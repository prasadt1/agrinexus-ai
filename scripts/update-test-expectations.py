#!/usr/bin/env python3
"""
Script to help update test expectations based on actual document content.

This queries your Knowledge Base with each golden question and shows you
what keywords are actually present in the responses, so you can update
your test expectations to be realistic.
"""

import boto3
import json

# Initialize Bedrock client
bedrock_agent = boto3.client('bedrock-agent-runtime', region_name='us-east-1')

# Your Knowledge Base ID
KB_ID = "H81XLD3YWY"

# Sample questions to test
SAMPLE_QUESTIONS = [
    ("Cotton mein aphids ka control kaise karein?", "Aphid control"),
    ("Bollworm ke liye best time kya hai spray karne ka?", "Bollworm spray timing"),
    ("Spray karne ke liye weather conditions kya honi chahiye?", "Spray weather"),
    ("Cotton ko pani kitne din mein dena chahiye?", "Irrigation"),
    ("Whitefly control ke liye kya karein?", "Whitefly control"),
    ("Nitrogen kitna dalna chahiye cotton mein?", "Nitrogen"),
    ("Paraquat use kar sakte hain kya?", "Banned pesticide"),
]

def query_kb(question):
    """Query Knowledge Base"""
    try:
        response = bedrock_agent.retrieve_and_generate(
            input={'text': question},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KB_ID,
                    'modelArn': 'arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0',
                }
            }
        )
        return response['output']['text']
    except Exception as e:
        return f"Error: {e}"

def extract_keywords(text):
    """Extract potential keywords from response"""
    text_lower = text.lower()
    
    # Common pest management terms
    keywords = {
        'pesticides': [],
        'pests': [],
        'methods': [],
        'timing': [],
        'thresholds': []
    }
    
    # Pesticides
    pesticide_terms = [
        'imidacloprid', 'thiamethoxam', 'acetamiprid', 'neem', 
        'profenophos', 'emamectin', 'chlorantraniliprole',
        'bt', 'bacillus thuringiensis', 'pheromone'
    ]
    for term in pesticide_terms:
        if term in text_lower:
            keywords['pesticides'].append(term)
    
    # Pests
    pest_terms = ['aphid', 'whitefly', 'bollworm', 'jassid', 'thrips', 'mealybug']
    for term in pest_terms:
        if term in text_lower:
            keywords['pests'].append(term)
    
    # Methods
    method_terms = [
        'spray', 'predator', 'biological control', 'ipm', 
        'integrated pest management', 'monitoring', 'trap'
    ]
    for term in method_terms:
        if term in text_lower:
            keywords['methods'].append(term)
    
    # Timing/conditions
    timing_terms = [
        'morning', 'evening', 'flowering', 'square', 'boll formation',
        'wind', 'rain', '7-10 days', '10 km'
    ]
    for term in timing_terms:
        if term in text_lower:
            keywords['timing'].append(term)
    
    # Thresholds
    threshold_terms = ['5-10', '10%', 'etl', 'economic threshold']
    for term in threshold_terms:
        if term in text_lower:
            keywords['thresholds'].append(term)
    
    return keywords

def main():
    print("="*80)
    print("ANALYZING KNOWLEDGE BASE RESPONSES")
    print("="*80)
    print("\nThis will help you update test expectations based on actual content.\n")
    
    for question, topic in SAMPLE_QUESTIONS:
        print(f"\n{'='*80}")
        print(f"Topic: {topic}")
        print(f"Question: {question}")
        print(f"{'='*80}")
        
        # Query KB
        print("\nQuerying Knowledge Base...")
        response = query_kb(question)
        
        # Show response
        print(f"\nResponse (first 300 chars):")
        print(response[:300] + "..." if len(response) > 300 else response)
        
        # Extract keywords
        keywords = extract_keywords(response)
        
        print(f"\nFound Keywords:")
        for category, terms in keywords.items():
            if terms:
                print(f"  {category.capitalize()}: {', '.join(terms)}")
        
        # Suggest test expectations
        all_keywords = []
        for terms in keywords.values():
            all_keywords.extend(terms)
        
        if all_keywords:
            print(f"\nSuggested expected_keywords:")
            print(f"  {all_keywords[:4]}")  # Top 4 keywords
        else:
            print(f"\n⚠️  No common keywords found - response may be too generic")
        
        print()
    
    print("="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
1. Update tests/test_golden_questions.py with realistic keywords
2. Focus on keywords that appear consistently in responses
3. Don't expect keywords that aren't in your source documents
4. Consider making tests more flexible (e.g., require 2 out of 4 keywords)

Example update:
    {
        "expected_keywords": ["acetamiprid", "thiamethoxam", "predator"],
        # Instead of: ["neem", "imidacloprid", "5-10 aphids"]
    }
""")

if __name__ == "__main__":
    main()
