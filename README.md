# Internship Notion Tracker

Automatically track internship application emails in Notion! This AWS Lambda function monitors your email inbox, identifies internship-related emails, and creates organized entries in your Notion database.

## 🎯 How It Works

1. **Email Reception**: AWS SES receives emails to your configured email address
2. **Storage**: SES stores the raw email in an S3 bucket
3. **Trigger**: SES triggers this Lambda function
4. **Processing**: Lambda analyzes the email for internship-related keywords
5. **Extraction**: Extracts company name, position, dates, and URLs
6. **Notion Integration**: Creates a new entry in your Notion database with all details

## 📋 Prerequisites

Before deploying this solution, you need:

### 1. AWS SES (Simple Email Service)
- **Verified domain or email address** for receiving emails
- **Email receiving rule** configured to:
  - Store emails in S3 bucket
  - Trigger Lambda function on email receipt
- **S3 action configured** in SES rule set to save to `emails/` prefix

### 2. AWS S3 Bucket
- **Bucket created** for storing incoming emails
- **Lambda permissions** to read from this bucket
- **SES permissions** to write to this bucket
- Recommended structure: `your-bucket/emails/{messageId}`

### 3. Notion Setup
- **Notion Integration** created at [Notion Integrations](https://www.notion.so/my-integrations)
- **Integration token** (API key) generated
- **Notion database** with the following properties:

#### Required Database Properties:
| Property Name | Type | Description |
|--------------|------|-------------|
| Position | Title | Job position/role name |
| Company | Rich Text | Company name |
| Status | Status | Application status (ensure "Applied" option exists) |
| Submission Date | Date | When application was submitted |
| Source Email | Email | Sender's email address |
| Last Updated | Date | Last modification date |

#### Optional Properties (commented out in code):
- Email Subject (Rich Text)
- Email Received Date (Date)  
- Application URL (URL)

- **Database shared** with your integration (click Share → Add your integration)
- **Database ID** (found in database URL: `notion.so/[workspace]/[DATABASE_ID]?v=...`)

### 4. AWS Lambda Setup
- **Python 3.x runtime** environment
- **Environment variables** configured:
  - `NOTION_API_KEY`: Your Notion integration token
  - `NOTION_DB_ID`: Your Notion database ID
  - `S3_BUCKET_NAME`: Your S3 bucket name
- **IAM role** with permissions:
  - Read from S3 bucket
  - CloudWatch Logs (for debugging)

## 🚀 Deployment

### Step 1: Create Lambda Function
```bash
# Create a deployment package
cd lambda
zip -r function.zip lambda.py

# Upload to AWS Lambda (or use AWS Console)
aws lambda create-function \
  --function-name internship-notion-tracker \
  --runtime python3.11 \
  --zip-file fileb://function.zip \
  --handler lambda.lambda_handler \
  --role arn:aws:iam::YOUR_ACCOUNT:role/YOUR_LAMBDA_ROLE
```

### Step 2: Configure Environment Variables
In Lambda console, add:
- `NOTION_API_KEY`: `secret_xxxxxxxxxxxxxxxxxxxxxx`
- `NOTION_DB_ID`: `xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
- `S3_BUCKET_NAME`: `your-email-bucket-name`

### Step 3: Set Up SES Email Receiving
1. Go to SES Console → Email Receiving → Rule Sets
2. Create a new rule:
   - **Recipients**: your-email@yourdomain.com
   - **Actions**: 
     - S3 Action: Store to bucket with prefix `emails/`
     - Lambda Action: Select your Lambda function

### Step 4: Grant Permissions
```bash
# Allow SES to invoke Lambda
aws lambda add-permission \
  --function-name internship-notion-tracker \
  --statement-id AllowSESInvoke \
  --action lambda:InvokeFunction \
  --principal ses.amazonaws.com

# Ensure Lambda role has S3 read access to your bucket
```

## 🔍 Email Filtering Logic

The function identifies internship emails using these keywords:
- internship, intern, application, applied
- interview, assessment
- "thank you for applying", "we received your application"
- position, opportunity, job, career, talent, recruiting
- next steps, coding challenge, offer, congratulations

**Note**: Only emails matching these keywords are added to Notion. Others are ignored.

## 📊 What Gets Extracted

From each email, the function extracts:

- **Position**: Derived from email subject or body (e.g., "Software Engineering Intern")
- **Company**: Extracted from sender name or email domain
- **Sender Email**: The from address
- **Submission Date**: Email received date
- **Status**: Automatically set to "Applied"
- **URLs**: Up to 5 URLs found in email body (first one used as application URL)

## 🛠️ Customization

### Adding More Keywords
Edit the `KEYWORDS` list in [lambda.py](lambda/lambda.py#L18-L23):
```python
KEYWORDS = [
    'internship', 'your-keyword-here',
    # Add more keywords
]
```

### Enabling Optional Properties
Uncomment sections in [lambda.py](lambda/lambda.py#L302-L318) to add:
- Email Subject
- Email Received Date
- Application URL

Make sure to add corresponding properties to your Notion database!

### Adjusting Email Body Preview
Change the snippet length in [lambda.py](lambda/lambda.py#L85):
```python
body_snippet=body[:500]  # Change 500 to your preferred length
```

## 🐛 Troubleshooting

### Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/internship-notion-tracker --follow
```

### Common Issues

**"No data sources found"**: 
- Ensure database is shared with your Notion integration
- Verify `NOTION_DB_ID` is correct

**"Failed to create Notion entry"**:
- Check that all required properties exist in database
- Verify property names match exactly (case-sensitive)
- Ensure "Applied" status option exists

**Emails not being processed**:
- Check SES rule is active
- Verify Lambda is being triggered (check CloudWatch)
- Review keyword matching in logs

## 📝 Testing

Send a test email to your SES-configured address with internship keywords:
```
Subject: Software Engineering Internship - Summer 2026
Body: Thank you for your application to our internship program...
```

Check CloudWatch logs and your Notion database for the new entry.

## 🔒 Security Notes

- Store `NOTION_API_KEY` securely (use AWS Secrets Manager for production)
- Restrict S3 bucket access to only Lambda and SES
- Use least-privilege IAM roles
- Enable Lambda function encryption

## 📄 License

This project is open source and available under the MIT License.

## 🤝 Contributing

Feel free to submit issues or pull requests to improve the functionality!
