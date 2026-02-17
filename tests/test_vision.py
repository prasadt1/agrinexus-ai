"""
Vision Test
Tests Claude 3 Sonnet Vision for crop pest/disease identification
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vision.analyzer import analyze_crop_image


def test_vision_analysis(image_path, dialect, crop, description):
    """Test vision analysis with a sample image"""
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"{'='*70}")
    print(f"Image: {image_path}")
    print(f"Dialect: {dialect}")
    print(f"Crop: {crop}")
    print(f"{'='*70}")
    
    # Read image
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        
        print(f"\n1. Image loaded: {len(image_bytes)} bytes")
        
        # Analyze
        print(f"\n2. Analyzing with Claude 3 Sonnet Vision...")
        result = analyze_crop_image(image_bytes, dialect, crop)
        
        # Display results
        print(f"\n3. ✓ Analysis complete!")
        print(f"\n{'='*70}")
        print(f"RESULTS")
        print(f"{'='*70}")
        print(f"\nDiagnosis: {result['diagnosis']}")
        print(f"Severity: {result['severity']}")
        print(f"Confidence: {result['confidence']}")
        print(f"\nRecommendations:")
        print(f"{result['recommendations']}")
        print(f"\n{'='*70}")
        
        if 'error' in result:
            print(f"\n⚠ Error occurred: {result['error']}")
            return False
        
        print(f"\n✓ TEST PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_vision.py <image_file> [dialect] [crop]")
        print("\nExample:")
        print("  python test_vision.py cotton-pest.jpg hi cotton")
        print("\nDialects: hi, mr, te, en")
        print("Crops: cotton, wheat, soybean, maize")
        print("\nTo test:")
        print("  1. Find a cotton pest/disease image online")
        print("  2. Download it (e.g., cotton-bollworm.jpg)")
        print("  3. Run: python tests/test_vision.py cotton-bollworm.jpg hi cotton")
        print("\nSample images you can search for:")
        print("  - 'cotton bollworm damage'")
        print("  - 'cotton aphid infestation'")
        print("  - 'cotton leaf curl disease'")
        print("  - 'cotton nutrient deficiency'")
        sys.exit(1)
    
    image_path = sys.argv[1]
    dialect = sys.argv[2] if len(sys.argv) > 2 else 'en'
    crop = sys.argv[3] if len(sys.argv) > 3 else 'cotton'
    
    # Validate file exists
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    
    # Validate dialect
    if dialect not in ['hi', 'mr', 'te', 'en']:
        print(f"Error: Invalid dialect: {dialect}")
        print("Valid dialects: hi, mr, te, en")
        sys.exit(1)
    
    # Run test
    description = f"{dialect.upper()} - {crop.title()} pest/disease identification"
    success = test_vision_analysis(image_path, dialect, crop, description)
    
    sys.exit(0 if success else 1)
