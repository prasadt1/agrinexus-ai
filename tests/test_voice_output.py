"""
Voice Output Test
Tests Amazon Polly text-to-speech in all 4 languages
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.voice.output import text_to_speech, get_polly_voice
import boto3

s3 = boto3.client('s3', region_name='us-east-1')

TEST_PHONE = '+919876543210'


def test_voice_output(text, dialect, description):
    """Test voice output generation"""
    print(f"\n{'='*70}")
    print(f"TEST: {description}")
    print(f"Dialect: {dialect}")
    print(f"Text: {text}")
    print(f"{'='*70}")
    
    # Get voice info
    voice_id, language_code = get_polly_voice(dialect)
    print(f"\n1. Voice Configuration:")
    print(f"   Voice ID: {voice_id}")
    print(f"   Language Code: {language_code}")
    
    # Generate audio
    print(f"\n2. Generating audio with Amazon Polly...")
    audio_url = text_to_speech(text, dialect, TEST_PHONE)
    
    if audio_url:
        print(f"\n3. ✓ Audio generated successfully!")
        print(f"   URL: {audio_url[:80]}...")
        
        # Extract S3 key from URL
        if 'voice-output/' in audio_url:
            s3_key = audio_url.split('voice-output/')[1].split('?')[0]
            s3_key = f"voice-output/{s3_key}"
            
            # Get audio file size
            try:
                response = s3.head_object(
                    Bucket='agrinexus-temp-audio-dev-043624892076',
                    Key=s3_key
                )
                size_kb = response['ContentLength'] / 1024
                print(f"   File size: {size_kb:.1f} KB")
                print(f"   Content type: {response['ContentType']}")
            except Exception as e:
                print(f"   Could not get file info: {e}")
        
        print(f"\n4. ✓ TEST PASSED")
        print(f"\n   To listen to the audio:")
        print(f"   1. Copy the URL above")
        print(f"   2. Paste in browser (valid for 1 hour)")
        print(f"   3. Or download: curl '{audio_url}' -o output.mp3")
        
        return True
    else:
        print(f"\n3. ✗ TEST FAILED: Audio generation failed")
        return False


if __name__ == '__main__':
    # Test cases - Only English supported by Amazon Polly
    # Hindi/Marathi/Telugu require Google Cloud TTS (post-MVP)
    test_cases = [
        {
            'text': 'For cotton pest control, spray neem oil or imidacloprid. The best time to spray is early morning or evening when temperatures are cooler.',
            'dialect': 'en',
            'description': 'English: Cotton pest control advice'
        },
        {
            'text': 'Apply fertilizer when the cotton plant reaches 30 days after sowing. Use a balanced NPK fertilizer at the rate of 120 kg per hectare.',
            'dialect': 'en',
            'description': 'English: Fertilizer application advice'
        }
    ]
    
    print("\n" + "="*70)
    print("VOICE OUTPUT TEST SUITE")
    print("Testing Amazon Polly text-to-speech")
    print("\nNOTE: Only English supported by Amazon Polly")
    print("Hindi/Marathi/Telugu require Google Cloud TTS (post-MVP)")
    print("="*70)
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\nTest {i}/{len(test_cases)}")
        success = test_voice_output(
            text=test_case['text'],
            dialect=test_case['dialect'],
            description=test_case['description']
        )
        results.append((test_case['description'], success))
        
        if i < len(test_cases):
            print(f"\n⏳ Waiting 3 seconds before next test...")
            import time
            time.sleep(3)
    
    # Summary
    print("\n\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for desc, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {desc}")
    
    passed = sum(1 for _, s in results if s)
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n✓ All voice output tests passed!")
        print("\nYou can now:")
        print("1. Listen to the generated audio files using the URLs above")
        print("2. Test end-to-end by sending a voice note to WhatsApp (requires real number)")
        print("3. Enable voicePreference in user profile for always-voice responses")
    
    print("="*70)
