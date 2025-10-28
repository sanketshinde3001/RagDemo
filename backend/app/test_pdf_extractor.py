"""
Test script for PDF extraction functionality
Demonstrates how to use the PDF extractor directly
"""

from app.utils.pdf_extractor import PDFExtractor, extract_pdf
import json
from pathlib import Path


def test_pdf_extraction(pdf_path: str):
    """
    Test PDF extraction with a sample PDF
    
    Args:
        pdf_path: Path to test PDF file
    """
    print("=" * 80)
    print("PDF EXTRACTION TEST")
    print("=" * 80)
    print(f"\nProcessing: {pdf_path}")
    print("-" * 80)
    
    # Check if file exists
    if not Path(pdf_path).exists():
        print(f"\n❌ ERROR: PDF file not found: {pdf_path}")
        print("\nTo test this script:")
        print("1. Place a PDF file in the backend directory")
        print("2. Run: python -m app.test_pdf_extractor your_file.pdf")
        return
    
    try:
        # Extract text and images
        doc_id = "test_doc_001"
        result = extract_pdf(
            pdf_path=pdf_path,
            doc_id=doc_id,
            output_dir="uploads/extracted"
        )
        
        # Display results
        print(f"\n✅ Extraction completed successfully!")
        print(f"\n📄 Document ID: {result['doc_id']}")
        print(f"📊 Total Pages: {result['total_pages']}")
        
        total_images = 0
        total_text_length = 0
        
        # Process each page
        for page in result['pages']:
            page_num = page['page_num']
            text = page['text']
            images = page['images']
            
            print(f"\n{'─' * 80}")
            print(f"📃 PAGE {page_num}")
            print(f"{'─' * 80}")
            
            # Text info
            text_preview = text[:200].replace('\n', ' ') if text else "(no text)"
            print(f"\n📝 Text Length: {len(text)} characters")
            print(f"   Preview: {text_preview}...")
            
            total_text_length += len(text)
            
            # Images info
            print(f"\n🖼️  Images Found: {len(images)}")
            for img in images:
                print(f"   • Image {img['img_num']}")
                print(f"     - Filename: {img['filename']}")
                print(f"     - Size: {img['width']}x{img['height']} pixels")
                print(f"     - Type: {img['type']}")
                if img['bbox']:
                    print(f"     - Position: x={img['bbox'][0]:.1f}, y={img['bbox'][1]:.1f}")
                print(f"     - Saved to: {img['filepath']}")
            
            total_images += len(images)
        
        # Summary
        print(f"\n{'=' * 80}")
        print("📊 EXTRACTION SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total Pages Processed: {result['total_pages']}")
        print(f"Total Text Characters: {total_text_length:,}")
        print(f"Total Images Extracted: {total_images}")
        print(f"Images saved in: uploads/extracted/")
        
        # Image type breakdown
        image_types = {}
        for page in result['pages']:
            for img in page['images']:
                img_type = img['type']
                image_types[img_type] = image_types.get(img_type, 0) + 1
        
        if image_types:
            print(f"\n📈 Image Type Breakdown:")
            for img_type, count in image_types.items():
                print(f"   • {img_type}: {count}")
        
        # Save results to JSON
        output_file = f"uploads/test_extraction_{doc_id}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Full results saved to: {output_file}")
        
        print(f"\n{'=' * 80}")
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print(f"{'=' * 80}\n")
        
    except Exception as e:
        print(f"\n❌ ERROR during extraction:")
        print(f"   {str(e)}")
        import traceback
        print(f"\n📋 Traceback:")
        print(traceback.format_exc())


def main():
    """Main entry point"""
    import sys
    
    print("\n🔧 PDF EXTRACTOR TEST UTILITY")
    print("=" * 80)
    
    if len(sys.argv) < 2:
        print("\n❓ Usage: python -m app.test_pdf_extractor <pdf_file_path>")
        print("\nExample:")
        print("  python -m app.test_pdf_extractor sample.pdf")
        print("  python -m app.test_pdf_extractor uploads/pdfs/document.pdf")
        print("\n" + "=" * 80 + "\n")
        
        # Try to find any PDF in current directory
        pdfs = list(Path(".").glob("*.pdf"))
        if pdfs:
            print(f"📁 Found PDF files in current directory:")
            for pdf in pdfs:
                print(f"   • {pdf}")
            print(f"\n💡 Try running: python -m app.test_pdf_extractor {pdfs[0]}")
        return
    
    pdf_path = sys.argv[1]
    test_pdf_extraction(pdf_path)


if __name__ == "__main__":
    main()
