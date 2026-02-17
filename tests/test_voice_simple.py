"""
Simple Voice Pipeline Test
Tests Transcribe with a sample audio file you provide
"""
import boto3
import json
import time
import sys

transcribe = boto3.client('transcribe', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')

TEMP_BUCKET = 'agrinexus-temp-audio-dev-043624892076'


def test_transcribe(audio_file_path, language='hi-IN'):
    """
    Test transcription with a local audio file
    
    Usage:
        python test_voice_simple.py path/to/audio.mp3 hi-IN
    
    Supported languages:
        hi-IN (Hindi)
        mr-IN (Marathi)
        te-IN (Telugu)
        en-IN (English)
    """
    print(f"Testing voice transcription...")
    print(f"Audio file: {audio_file_path}")
    print(f"Language: {language}")
    print("-" * 60)
    
    # Upload to S3
    timestamp = int(time.time())
    s3_key = f"test/voice-test-{timestamp}.mp3"
    
    print(f"\n1. Uploading to S3...")
    s3.upload_file(audio_file_path, TEMP_BUCKET, s3_key)
    s3_uri = f"s3://{TEMP_BUCKET}/{s3_key}"
    print(f"   ✓ Uploaded: {s3_uri}")
    
    # Start transcription
    job_name = f"test-{timestamp}"
    print(f"\n2. Starting transcription job: {job_name}")
    
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': s3_uri},
        MediaFormat='mp3',
        LanguageCode=language
    )
    
    print(f"   ⏳ Waiting for completion...")
    
    # Poll for result
    for attempt in range(60):
        time.sleep(2)
        result = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        status = result['TranscriptionJob']['TranscriptionJobStatus']
        
        if status == 'COMPLETED':
            # Get transcript
            import urllib.request
            transcript_uri = result['TranscriptionJob']['Transcript']['TranscriptFileUri']
            req = urllib.request.Request(transcript_uri)
            with urllib.request.urlopen(req) as response:
                transcript_data = json.loads(response.read())
            
            transcript_text = transcript_data['results']['transcripts'][0]['transcript']
            
            # Calculate confidence
            items = transcript_data['results']['items']
            confidences = [
                float(item['alternatives'][0]['confidence'])
                for item in items
                if 'confidence' in item.get('alternatives', [{}])[0]
            ]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            print(f"\n3. ✓ Transcription complete!")
            print(f"\n" + "=" * 60)
            print(f"TRANSCRIPT: {transcript_text}")
            print(f"CONFIDENCE: {avg_confidence:.2%}")
            print("=" * 60)
            
            if avg_confidence >= 0.5:
                print(f"\n✓ PASS: Confidence above threshold (0.5)")
            else:
                print(f"\n⚠ WARNING: Low confidence (below 0.5)")
            
            # Cleanup
            print(f"\n4. Cleaning up...")
            transcribe.delete_transcription_job(TranscriptionJobName=job_name)
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
            print(f"   ✓ Deleted transcription job and S3 object")
            
            return transcript_text, avg_confidence
        
        elif status == 'FAILED':
            error = result['TranscriptionJob'].get('FailureReason', 'Unknown error')
            print(f"\n✗ FAILED: {error}")
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
            return None, 0.0
        
        print(f"   ⏳ Status: {status} (attempt {attempt + 1}/60)")
    
    print(f"\n✗ TIMEOUT: Transcription took too long")
    s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
    return None, 0.0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_voice_simple.py <audio_file.mp3> [language]")
        print("\nExample:")
        print("  python test_voice_simple.py my_voice_note.mp3 hi-IN")
        print("\nSupported languages:")
        print("  hi-IN (Hindi)")
        print("  mr-IN (Marathi)")
        print("  te-IN (Telugu)")
        print("  en-IN (English)")
        print("\nTo create a test audio file:")
        print("  1. Record yourself saying: 'कपास में कीट कैसे नियंत्रित करें'")
        print("  2. Save as MP3 or convert using: ffmpeg -i input.m4a output.mp3")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else 'hi-IN'
    
    test_transcribe(audio_file, language)
