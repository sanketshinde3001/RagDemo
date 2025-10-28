from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from app.schemas.item import Item, ItemCreate, ItemUpdate
from app.schemas.pdf import PDFUploadResponse, ProcessingStatus, ChatRequest, ChatResponse, ContextChunk
from app.utils.pdf_extractor import extract_pdf
from app.utils.gemini_vision import analyze_pdf_images, GeminiVisionAnalyzer
from app.utils.text_chunker import chunk_pdf_extraction
from app.utils.supabase_storage import get_storage_client
from app.utils.pinecone_storage import get_pinecone_storage
from app.utils.chat_storage import chat_storage
from app.utils.query_classifier import QueryClassifier
from app.utils.web_search import web_search
from app.utils.deepgram_stt import create_deepgram_transcriber
from app.core.config import settings
from typing import List
import google.generativeai as genai
import uuid
import aiofiles
from pathlib import Path
import logging
import tempfile
import os
import json
import asyncio
from app.utils.pdf_extractor import extract_pdf
from app.utils.gemini_vision import analyze_pdf_images, GeminiVisionAnalyzer
from app.utils.text_chunker import chunk_pdf_extraction
from app.utils.supabase_storage import get_storage_client
from app.utils.pinecone_storage import get_pinecone_storage
from app.utils.chat_storage import chat_storage
from app.utils.query_classifier import get_query_classifier
from app.utils.web_search import get_web_searcher
from app.core.config import settings
from typing import List
import google.generativeai as genai
import uuid
import aiofiles
from pathlib import Path
import logging
import tempfile
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory storage for demonstration
items_db = {}
item_id_counter = 1


@router.get("/items", response_model=List[Item], tags=["items"])
async def get_items():
    """Get all items"""
    return list(items_db.values())


@router.get("/items/{item_id}", response_model=Item, tags=["items"])
async def get_item(item_id: int):
    """Get a specific item by ID"""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    return items_db[item_id]


@router.post("/items", response_model=Item, status_code=201, tags=["items"])
async def create_item(item: ItemCreate):
    """Create a new item"""
    global item_id_counter
    new_item = Item(
        id=item_id_counter,
        name=item.name,
        description=item.description,
        price=item.price
    )
    items_db[item_id_counter] = new_item
    item_id_counter += 1
    return new_item


@router.put("/items/{item_id}", response_model=Item, tags=["items"])
async def update_item(item_id: int, item: ItemUpdate):
    """Update an existing item"""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    
    stored_item = items_db[item_id]
    update_data = item.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(stored_item, field, value)
    
    return stored_item


# ============================================
# PDF PROCESSING ENDPOINTS
# ============================================

@router.post("/upload-pdf", response_model=PDFUploadResponse, tags=["pdf"])
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: str = None  # Optional session ID for chat tracking
):
    """
    Upload and process a PDF file
    
    - Accepts PDF file upload
    - Extracts text page-by-page with page numbers
    - Extracts all images with bounding boxes
    - Classifies images (chart/diagram vs photo)
    - Saves images to Supabase Storage
    - Generates embeddings and stores in Pinecone with session tracking
    
    Args:
        file: PDF file to upload
        session_id: Optional session ID to group documents for isolated search
    
    Returns:
        PDFUploadResponse with doc_id, processing status, and extraction results
    """
    
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(
            status_code=400, 
            detail="Only PDF files are accepted"
        )
    
    try:
        # Generate unique document ID and session ID if not provided
        doc_id = str(uuid.uuid4())[:8]
        if not session_id:
            session_id = str(uuid.uuid4())[:12]  # Generate session ID
        
        logger.info(f"Processing PDF - doc_id: {doc_id}, session_id: {session_id}")
        
        # Save PDF temporarily for processing
        temp_dir = tempfile.mkdtemp()
        temp_pdf_path = os.path.join(temp_dir, f"{doc_id}_{file.filename}")
        
        # Save file content
        content = await file.read()
        async with aiofiles.open(temp_pdf_path, 'wb') as out_file:
            await out_file.write(content)
        
        logger.info(f"PDF saved temporarily: {temp_pdf_path}")
        
        # Upload PDF to Supabase Storage
        storage_client = get_storage_client()
        pdf_storage_path = f"pdfs/{doc_id}/{file.filename}"
        pdf_upload_result = storage_client.upload_file(
            file_path=temp_pdf_path,
            storage_path=pdf_storage_path,
            content_type='application/pdf'
        )
        logger.info(f"✓ PDF uploaded to Supabase: {pdf_upload_result['url']}")
        
        # Extract text and images (images will be uploaded to Supabase automatically)
        extraction_result = extract_pdf(
            pdf_path=temp_pdf_path,
            doc_id=doc_id,
            use_supabase=True  # Upload images to Supabase
        )
        
        # Add PDF URL and session info to extraction result
        extraction_result['pdf_url'] = pdf_upload_result['url']
        extraction_result['pdf_storage_path'] = pdf_upload_result['path']
        extraction_result['session_id'] = session_id
        extraction_result['filename'] = file.filename
        
        # Clean up temp file
        try:
            os.remove(temp_pdf_path)
            os.rmdir(temp_dir)
        except:
            pass
        
        # Count total images
        total_images = sum(len(page['images']) for page in extraction_result['pages'])
        
        logger.info(f"Extraction complete for {doc_id}: "
                   f"{extraction_result['total_pages']} pages, {total_images} images")
        
        # Analyze images with Gemini Vision if API key is configured
        if settings.GOOGLE_API_KEY and total_images > 0:
            try:
                logger.info(f"Starting Gemini vision analysis for {total_images} images")
                extraction_result = analyze_pdf_images(
                    extraction_result,
                    api_key=settings.GOOGLE_API_KEY
                )
                logger.info("✓ Gemini vision analysis complete")
            except Exception as e:
                logger.warning(f"Gemini analysis failed (continuing without it): {e}")
        elif not settings.GOOGLE_API_KEY:
            logger.warning("GOOGLE_API_KEY not set - skipping image analysis")
        
        # Add semantic chunking WITH EMBEDDINGS
        logger.info("Starting semantic text chunking with embeddings")
        extraction_result = chunk_pdf_extraction(
            extraction_result,
            chunk_size=500,
            chunk_overlap=50,
            generate_embeddings=True  # Generate embeddings for chunks
        )
        total_chunks = extraction_result.get('total_chunks', 0)
        logger.info(f"✓ Created {total_chunks} text chunks with embeddings")
        
        # Store in Pinecone
        logger.info("Storing vectors in Pinecone...")
        pinecone_storage = get_pinecone_storage()
        storage_result = pinecone_storage.store_document(
            extraction_result,
            namespace=None  # Use default namespace
        )
        logger.info(f"✓ Stored {storage_result['total_vectors']} vectors in Pinecone")
        logger.info(f"✓ Session ID for this upload: {storage_result['session_id']}")
        
        # Add storage info to response
        extraction_result['pinecone_storage'] = storage_result
        
        return PDFUploadResponse(
            success=True,
            message=f"PDF processed and stored successfully ({storage_result['total_vectors']} vectors)",
            doc_id=doc_id,
            session_id=session_id,  # Return session_id to frontend!
            filename=file.filename,
            total_pages=extraction_result['total_pages'],
            total_images=total_images,
            extraction_result=extraction_result
        )
        
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PDF: {str(e)}"
        )


@router.get("/processing-status/{doc_id}", response_model=ProcessingStatus, tags=["pdf"])
async def get_processing_status(doc_id: str):
    """
    Get processing status for a document
    
    Args:
        doc_id: Document identifier
        
    Returns:
        ProcessingStatus with current status
    """
    # This is a simple implementation
    # In production, you'd track status in a database or cache
    
    pdf_path = Path(f"uploads/pdfs") / f"{doc_id}_*.pdf"
    
    # Check if PDF exists (simple check)
    import glob
    matching_files = glob.glob(str(pdf_path))
    
    if not matching_files:
        raise HTTPException(
            status_code=404,
            detail=f"Document {doc_id} not found"
        )
    
    return ProcessingStatus(
        doc_id=doc_id,
        status="completed",
        progress=100.0,
        message="Processing completed successfully"
    )


# ============================================
# CHAT / RAG ENDPOINTS
# ============================================

@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat_with_documents(request: ChatRequest):
    """
    Intelligent chat endpoint with query routing
    
    - Classifies query type (greeting, document, web_search)
    - Simple greetings get instant responses
    - Document questions use RAG retrieval from Pinecone
    - Web search queries use SerpAPI
    - Maintains conversation history in Supabase
    
    Args:
        request: ChatRequest with query and session_id
        
    Returns:
        ChatResponse with generated answer, context, and sources
    """
    try:
        logger.info(f"Chat query: '{request.query}' (session: {request.session_id})")
        
        # 1. Classify the query
        classifier = get_query_classifier()
        
        # Check if user has documents (we'll check if Pinecone returns results)
        # For now, assume they have docs if session_id is provided
        has_documents = bool(request.session_id)
        
        classification = classifier.classify(request.query, has_documents)
        query_type = classification['type']
        
        logger.info(f"Query classified as: {query_type} (confidence: {classification['confidence']:.2f}) - {classification['reason']}")
        
        # 2. Handle based on query type
        
        # === GREETING HANDLER ===
        if query_type == 'greeting':
            answer = classifier.get_greeting_response(request.query)
            
            # Save messages
            chat_storage.save_message(
                session_id=request.session_id,
                role="user",
                message=request.query
            )
            
            chat_storage.save_message(
                session_id=request.session_id,
                role="assistant",
                message=answer,
                metadata={'query_type': 'greeting'}
            )
            
            return ChatResponse(
                answer=answer,
                context=[],
                session_id=request.session_id,
                query=request.query,
                sources=[]
            )
        
        # === WEB SEARCH HANDLER ===
        elif query_type == 'web_search':
            web_searcher = get_web_searcher()
            search_results = web_searcher.search(request.query, num_results=5)
            
            if not search_results['success']:
                answer = f"I'd like to search the web for that, but web search is not configured. {search_results.get('error', '')}"
                
                chat_storage.save_message(session_id=request.session_id, role="user", message=request.query)
                chat_storage.save_message(session_id=request.session_id, role="assistant", message=answer)
                
                return ChatResponse(
                    answer=answer,
                    context=[],
                    session_id=request.session_id,
                    query=request.query,
                    sources=[]
                )
            
            # Format web results as context
            web_context = web_searcher.format_results_for_context(search_results['results'])
            
            # Load chat history
            chat_history = chat_storage.get_recent_context(session_id=request.session_id, num_turns=3)
            
            # Save user message
            chat_storage.save_message(session_id=request.session_id, role="user", message=request.query)
            
            # Generate answer with Gemini
            if not settings.GOOGLE_API_KEY:
                raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not configured")
            
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Build history text
            history_text = ""
            if chat_history:
                history_parts = ["Previous conversation:"]
                for msg in chat_history[-6:]:
                    role = msg.get('role', 'user')
                    message = msg.get('message', '')
                    history_parts.append(f"{role.capitalize()}: {message}")
                history_text = "\n".join(history_parts)
            
            prompt = f"""You are a helpful AI assistant. Answer the user's question based on the web search results provided.

{history_text if history_text else ''}

{web_context}

User Question: {request.query}

Instructions:
- Answer based on the web search results
- Cite sources by mentioning the website names
- Be concise and informative
- If the results don't fully answer the question, say so

Answer:"""
            
            response = model.generate_content(prompt)
            answer = response.text
            
            # Save assistant response
            chat_storage.save_message(
                session_id=request.session_id,
                role="assistant",
                message=answer,
                metadata={
                    'query_type': 'web_search',
                    'num_results': len(search_results['results'])
                }
            )
            
            # Format sources
            sources = []
            for result in search_results['results']:
                sources.append({
                    'url': result['link'],
                    'filename': result['title'],
                    'pages': []
                })
            
            return ChatResponse(
                answer=answer,
                context=[],
                session_id=request.session_id,
                query=request.query,
                sources=sources
            )
        
        # === DOCUMENT RAG HANDLER ===
        else:  # query_type == 'document'
            # 1. Retrieve relevant context from Pinecone (RAG retrieval)
            logger.info(f"🔍 Searching Pinecone with session_id: {request.session_id}")
            
            pinecone_storage = get_pinecone_storage()
            results = pinecone_storage.query(
                query_text=request.query,
                top_k=request.top_k,
                session_id=request.session_id,  # Filter by session
                include_text=True
            )
            
            if not results:
                # No context found - save the query and return helpful message
                chat_storage.save_message(
                    session_id=request.session_id,
                    role="user",
                    message=request.query
                )
                
                no_context_answer = "I couldn't find any relevant information in the uploaded documents for this session. Please make sure you've uploaded documents first."
                
                chat_storage.save_message(
                    session_id=request.session_id,
                    role="assistant",
                    message=no_context_answer
                )
                
                return ChatResponse(
                    answer=no_context_answer,
                    context=[],
                    session_id=request.session_id,
                    query=request.query,
                    sources=[]
                )
            
            logger.info(f"✓ Retrieved {len(results)} relevant chunks from Pinecone")
            
            # 2. Load conversation history from Supabase
            chat_history = chat_storage.get_recent_context(
                session_id=request.session_id,
                num_turns=5  # Last 5 conversation turns
            )
            
            logger.info(f"✓ Loaded {len(chat_history)} messages from history")
            
            # 3. Save user message to Supabase
            chat_storage.save_message(
                session_id=request.session_id,
                role="user",
                message=request.query
            )
            
            # 4. Generate answer using Gemini with context and history
            if not settings.GOOGLE_API_KEY:
                raise HTTPException(
                    status_code=500,
                    detail="GOOGLE_API_KEY not configured"
                )
            
            gemini = GeminiVisionAnalyzer(api_key=settings.GOOGLE_API_KEY)
            
            response_data = gemini.chat_with_context(
                query=request.query,
                context_chunks=results,
                chat_history=chat_history,
                max_context_length=8000
            )
            
            if not response_data['success']:
                raise HTTPException(status_code=500, detail="Failed to generate answer")
            
            answer = response_data['answer']
            sources = response_data['sources']
            
            logger.info(f"✓ Generated answer ({len(answer)} chars) with {len(sources)} sources")
            
            # 5. Save assistant response to Supabase
            chat_storage.save_message(
                session_id=request.session_id,
                role="assistant",
                message=answer,
                metadata={
                    'num_chunks': len(results),
                    'sources': sources,
                    'model': 'gemini-2.0-flash-exp',
                    'query_type': 'document'
                }
            )
            
            # 6. Format context chunks for response
            context_chunks = []
            for result in results:
                context_chunks.append(ContextChunk(
                    text=result.get('text', ''),
                    score=result.get('score', 0.0),
                    doc_id=result.get('metadata', {}).get('doc_id', ''),
                    page_num=result.get('page_num'),
                    pdf_url=result.get('pdf_url'),
                    type=result.get('type', 'text_chunk')
                ))
            
            return ChatResponse(
                answer=answer,
                context=context_chunks,
                session_id=request.session_id,
                query=request.query,
                sources=sources  # Add sources to response
            )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error generating answer: {str(e)}"
        )


@router.delete("/items/{item_id}", status_code=204, tags=["items"])
async def delete_item(item_id: int):
    """Delete an item"""
    if item_id not in items_db:
        raise HTTPException(status_code=404, detail="Item not found")
    del items_db[item_id]
    return None


# ============================================
# DEBUG ENDPOINTS
# ============================================

@router.get("/debug/pinecone-stats", tags=["debug"])
async def get_pinecone_stats(session_id: str = None):
    """
    Get Pinecone index statistics and sample vectors
    Helps debug session_id issues
    """
    try:
        pinecone_storage = get_pinecone_storage()
        
        # Get index stats
        stats = pinecone_storage.index.describe_index_stats()
        
        # Convert stats to dict manually
        result = {
            "index_name": pinecone_storage.index_name,
            "total_vectors": int(stats.total_vector_count) if stats.total_vector_count else 0,
            "dimension": int(stats.dimension) if stats.dimension else 0,
        }
        
        # If session_id provided, try to query
        if session_id:
            results = pinecone_storage.query(
                query_text="test",
                top_k=5,
                session_id=session_id
            )
            result["session_query_results"] = len(results)
            result["session_id_tested"] = session_id
            
            # Also try without session filter to see what's actually in DB
            all_results = pinecone_storage.index.query(
                vector=[0.0] * 1024,  # dummy vector
                top_k=10,
                include_metadata=True
            )
            
            # Extract unique session_ids from results
            session_ids = set()
            sample_vectors = []
            for match in all_results.matches:
                if hasattr(match, 'metadata') and match.metadata:
                    if 'session_id' in match.metadata:
                        session_ids.add(match.metadata['session_id'])
                    sample_vectors.append({
                        'id': match.id,
                        'session_id': match.metadata.get('session_id', 'N/A'),
                        'doc_id': match.metadata.get('doc_id', 'N/A'),
                        'type': match.metadata.get('type', 'N/A')
                    })
            
            result["session_ids_in_db"] = list(session_ids)
            result["sample_vectors"] = sample_vectors[:5]  # Show first 5
            result["total_vectors_sampled"] = len(all_results.matches)
        
        return result
        
    except Exception as e:
        logger.error(f"Error getting Pinecone stats: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# WEBSOCKET ENDPOINTS - VOICE TRANSCRIPTION
# ============================================

@router.websocket("/ws/transcribe")
async def websocket_transcribe(websocket: WebSocket):
    """
    WebSocket endpoint for real-time speech-to-text
    
    Client sends: Audio chunks (binary)
    Server sends: JSON messages with transcripts
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established: {websocket.client}")
    
    transcriber = None
    transcript_buffer = []
    
    try:
        # Initialize Deepgram transcriber (create new instance per connection)
        transcriber = create_deepgram_transcriber()
        
        # Callback for transcripts
        async def on_transcript(text: str, is_final: bool):
            """Send transcript back to client"""
            try:
                await websocket.send_json({
                    "type": "transcript",
                    "text": text,
                    "is_final": is_final,
                    "timestamp": asyncio.get_event_loop().time()
                })
                
                if is_final:
                    transcript_buffer.append(text)
                    logger.info(f"Final transcript: {text}")
                    
            except Exception as e:
                logger.error(f"Error sending transcript: {e}")
        
        # Callback for errors
        async def on_error(error_msg: str):
            """Send error to client"""
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": error_msg
                })
            except Exception as e:
                logger.error(f"Error sending error message: {e}")
        
        # Start Deepgram transcription
        logger.info("Starting Deepgram transcription...")
        success = await transcriber.start_transcription(
            on_transcript=on_transcript,
            on_error=on_error,
            language="en",
            model="nova-2",
            smart_format=True
        )
        
        if not success:
            await websocket.send_json({
                "type": "error",
                "message": "Failed to start Deepgram transcription service"
            })
            await websocket.close()
            return
        
        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "message": "Transcription service ready. Start speaking!"
        })
        logger.info("✓ Transcription service ready")
        
        # Listen for audio data
        while True:
            try:
                # Receive audio chunk or control message
                data = await websocket.receive()
                
                if "bytes" in data:
                    # Audio data - send to Deepgram
                    audio_chunk = data["bytes"]
                    await transcriber.send_audio(audio_chunk)
                    
                elif "text" in data:
                    # Control message
                    message = json.loads(data["text"])
                    command = message.get("command")
                    
                    if command == "stop":
                        # Stop transcription and return full transcript
                        full_transcript = " ".join(transcript_buffer)
                        
                        await websocket.send_json({
                            "type": "complete",
                            "full_transcript": full_transcript
                        })
                        
                        transcript_buffer.clear()
                        logger.info(f"Transcript completed: {full_transcript}")
                    
                    elif command == "ping":
                        await websocket.send_json({
                            "type": "pong"
                        })
                    
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected by client")
                break
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
                except:
                    pass
                break
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Transcription failed: {str(e)}"
            })
        except:
            pass
    
    finally:
        # Cleanup
        if transcriber:
            try:
                await transcriber.stop_transcription()
            except Exception as e:
                logger.error(f"Error stopping transcriber: {e}")
        
        try:
            await websocket.close()
        except:
            pass
        
        logger.info("WebSocket connection closed and cleaned up")
