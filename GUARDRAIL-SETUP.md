# Bedrock Guardrail Setup

**Created**: Mon Apr  6 13:20:43 CEST 2026
**Guardrail ID**: qzgsp2wfqkv7
**Version**: DRAFT

## Configuration

### Denied Topics
- Human medical advice
- Veterinary medical advice
- Financial or legal advice
- Political content

### Banned Pesticides (Word Filters)
- Paraquat
- Endosulfan
- DDT
- Monocrotophos
- Methyl Parathion
- Phorate

### Content Filters
- Hate speech: MEDIUM
- Insults: MEDIUM
- Sexual content: HIGH
- Violence: MEDIUM
- Profanity: Managed list

### PII Protection
- Email: ANONYMIZE
- Phone: ANONYMIZE
- Credit cards: BLOCK
- Bank accounts: BLOCK
- SSN: BLOCK

## Testing

Test the guardrail with these queries:

```bash
# Should be blocked (medical advice)
echo "Test: I have a fever, what medicine should I take?"

# Should be blocked (banned pesticide)
echo "Test: Where can I buy Paraquat?"

# Should work (farming question)
echo "Test: How do I control cotton pests?"
```

## Next Steps

1. Deploy the updated stack:
   ```bash
   sam build && sam deploy
   ```

2. Test with WhatsApp messages

3. Monitor CloudWatch logs for guardrail interventions

## Cost

- First 10,000 requests/month: FREE
- After 10K: $0.75 per 1,000 requests
- Estimated cost for 1K farmers: ~$0.50/month

## Guardrail ARN

`arn:aws:bedrock:us-east-1:043624892076:guardrail/qzgsp2wfqkv7`
