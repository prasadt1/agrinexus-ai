"""
End-to-End Voice Test
Simulates: Voice Input → Transcribe → RAG → Voice Output
"""
import sys
import os
import time
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.voice.output import text_to_speech
import boto3

transcribe = boto3.client('transcribe', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

TEMP_BUCKET = 'agrinexus-temp-audio-dev-043624892076'
KB_ID = 'H81XLD3YWY'
TEST_PHONE = '+919876543210'


def step1_record_or_use_existing(audio_file_path, dialect):
    """Step 1: Use your recorded audio file"""
    print(f"\n{'='*70}")
    print(f"STEP 1: Voice Input")
    print(f"{'='*70}")
    print(f"Using audio file: {audio_file_path}")
    print(f"Dialect: {dialect}")
    return audio_file_path


def step2_transcribe(audio_file_path, dialect):
    """Step 2: Transcribe audio to text"""
    print(f"\n{'='*70}")
    print(f"STEP 2: Transcribe (Amazon Transcribe)")
    print(f"{'='*70}")
    
    # Map dialect to language code
    lang_map = {'hi': 'hi-IN', 'mr': 'mr-IN', 'te': 'te-IN', 'en': 'en-IN'}
    language_code = lang_map.get(dialect, 'hi-IN')
    
    # Upload to S3
    timestamp = int(time.time())
    s3_key = f"test/voice-e2e-{timestamp}.mp3"
    
    print(f"Uploading to S3...")
    s3.upload_file(audio_file_path, TEMP_BUCKET, s3_key)
    s3_uri = f"s3://{TEMP_BUCKET}/{s3_key}"
    print(f"✓ Uploaded: {s3_uri}")
    
    # Start transcription
    job_name = f"e2e-test-{timestamp}"
    print(f"\nStarting transcription job: {job_name}")
    print(f"Language: {language_code}")
    
    transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={'MediaFileUri': s3_uri},
        MediaFormat='mp3',
        LanguageCode=language_code
    )
    
    print(f"⏳ Waiting for transcription...")
    
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
            
            print(f"\n✓ Transcription complete!")
            print(f"Text: '{transcript_text}'")
            print(f"Confidence: {avg_confidence:.2%}")
            
            # Cleanup
            transcribe.delete_transcription_job(TranscriptionJobName=job_name)
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
            
            return transcript_text, avg_confidence
        
        elif status == 'FAILED':
            print(f"✗ Transcription failed")
            s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
            return None, 0.0
    
    print(f"✗ Transcription timeout")
    s3.delete_object(Bucket=TEMP_BUCKET, Key=s3_key)
    return None, 0.0


def step3_rag_query(question, dialect):
    """Step 3: Query Bedrock Knowledge Base"""
    print(f"\n{'='*70}")
    print(f"STEP 3: RAG Query (Bedrock Knowledge Base)")
    print(f"{'='*70}")
    print(f"Question: {question}")
    
    # Map dialect to language instruction
    language_instructions = {
        'hi': 'Respond in Hindi (Devanagari script). Use simple, practical language.',
        'mr': 'Respond in Marathi (Devanagari script). Use simple, practical language.',
        'te': 'Respond in Telugu script. Use simple, practical language.',
        'en': 'Respond in English. Use simple, practical language suitable for Indian farmers.'
    }
    
    language_instruction = language_instructions.get(dialect, language_instructions['hi'])
    
    print(f"\n⏳ Querying Bedrock Knowledge Base...")
    
    response = bedrock_agent.retrieve_and_generate(
        input={'text': question},
        retrieveAndGenerateConfiguration={
            'type': 'KNOWLEDGE_BASE',
            'knowledgeBaseConfiguration': {
                'knowledgeBaseId': KB_ID,
                'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                'generationConfiguration': {
                    'promptTemplate': {
                        'textPromptTemplate': f'''You are an agricultural extension agent helping smallholder farmers in India. 
{language_instruction}
Include source citations.

Question: $query$

Context: $search_results$

Provide actionable advice with source references.'''
                    }
                }
            }
        }
    )
    
    answer = response['output']['text']
    print(f"\n✓ RAG response received!")
    print(f"Answer preview: {answer[:150]}...")
    
    return answer


def step4_text_to_speech(text, dialect):
    """Step 4: Convert response to speech"""
    print(f"\n{'='*70}")
    print(f"STEP 4: Voice Output (Amazon Polly)")
    print(f"{'='*70}")
    
    if dialect == 'te':
        print(f"⚠ Telugu voice not supported - would send text response")
        return None
    
    print(f"Generating voice output...")
    audio_url = text_to_speech(text, dialect, TEST_PHONE)
    
    if audio_url:
        print(f"\n✓ Voice output generated!")
        print(f"URL: {audio_url[:80]}...")
        return audio_url
    else:
        print(f"✗ Voice generation failed")
        return None


def run_end_to_end_test(audio_file_path, dialect, description):
    """Run complete end-to-end voice test"""
    
    print("\n" + "="*70)
    print(f"END-TO-END VOICE TEST: {description}")
    print("="*70)
    print(f"Flow: Voice Input → Transcribe → RAG → Voice Output")
    print("="*70)
    
    try:
        # Step 1: Use audio file
        step1_record_or_use_existing(audio_file_path, dialect)
        
        # Step 2: Transcribe
        transcript, confidence = step2_transcribe(audio_file_path, dialect)
        if not transcript:
            print("\n✗ TEST FAILED: Transcription failed")
            return False
        
        # Step 3: RAG Query
        answer = step3_rag_query(transcript, dialect)
        
        # Step 4: Text-to-Speech
        audio_url = step4_text_to_speech(answer, dialect)
        
        # Summary
        print(f"\n{'='*70}")
        print(f"TEST COMPLETE")
        print(f"{'='*70}")
        print(f"\n✓ Voice Input: {transcript}")
        print(f"✓ Confidence: {confidence:.2%}")
        print(f"✓ RAG Answer: {answer[:100]}...")
        
        if audio_url:
            print(f"✓ Voice Output: {audio_url[:80]}...")
            print(f"\n🎧 To listen to the response:")
            print(f"   Copy this URL and paste in browser:")
            print(f"   {audio_url}")
            print(f"\n   Or download:")
            print(f"   curl '{audio_url}' -o response.mp3")
            print(f"   open response.mp3")
        else:
            print(f"⚠ Voice Output: Text-only (Telugu or generation failed)")
        
        print(f"\n{'='*70}")
        print(f"✓ END-TO-END TEST PASSED")
        print(f"{'='*70}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python test_voice_end_to_end.py <audio_file.mp3> <dialect>")
        print("\nExample:")
        print("  python test_voice_end_to_end.py ~/Downloads/hindi-cotton-pest-question.mp3 hi")
        print("\nDialects:")
        print("  hi - Hindi")
        print("  mr - Marathi")
        print("  te - Telugu")
        print("  en - English")
        print("\nThis will:")
        print("  1. Transcribe your voice note")
        print("  2. Query Bedrock Knowledge Base")
        print("  3. Generate voice response")
        print("  4. Give you URL to listen to the response")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    dialect = sys.argv[2]
    
    # Validate file exists
    if not os.path.exists(audio_file):
        print(f"Error: Audio file not found: {audio_file}")
        sys.exit(1)
    
    # Validate dialect
    if dialect not in ['hi', 'mr', 'te', 'en']:
        print(f"Error: Invalid dialect: {dialect}")
        print("Valid dialects: hi, mr, te, en")
        sys.exit(1)
    
    # Run test
    description = f"{dialect.upper()} voice round-trip"
    success = run_end_to_end_test(audio_file, dialect, description)
    
    sys.exit(0 if success else 1)
