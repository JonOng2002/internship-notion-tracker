import json
import boto3
import email
import re
import os
from email import policy
from email.parser import BytesParser
from datetime import datetime
from urllib.parse import unquote_plus
import urllib.request
import urllib.parse

# Initialize S3 client
s3 = boto3.client('s3')

# Notion configuration
NOTION_API_KEY = os.environ['NOTION_API_KEY']
NOTION_DB_ID = os.environ['NOTION_DB_ID']
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']
NOTION_API_URL = "https://api.notion.com/v1/pages"

# Keywords to identify internship/application emails
KEYWORDS = [
    'internship', 'application', 'applied', 'interview', 'assessment',
    'thank you for applying', 'we received your application',
    'position', 'opportunity', 'job', 'career', 'talent', 'recruiting',
    'next steps', 'coding challenge', 'offer', 'congratulations'
]

def lambda_handler(event, context):
    """
    Main Lambda handler for processing SES emails stored in S3
    """
    try:
        print("Event received:", json.dumps(event))
        
        # Extract S3 bucket and key from SES event
        ses_notification = event['Records'][0]['ses']
        message_id = ses_notification['mail']['messageId']
        
        # Get S3 object key (SES stores with message ID)
        s3_key = message_id
        full_key = f"emails/{message_id}"
        
        print(f"Processing email from S3: {S3_BUCKET_NAME}/{full_key}")
        
        # Get email from S3
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=full_key)
        email_content = response['Body'].read()
        
        # Parse email
        msg = BytesParser(policy=policy.default).parsebytes(email_content)
        
        # Extract email details
        subject = msg['subject'] or "No Subject"
        from_email = msg['from'] or "Unknown"
        to_email = msg['to'] or ""
        date_str = msg['date'] or ""
        
        # Extract sender email from "From" field
        sender_email = extract_email_address(from_email)
        
        # Get email body
        body = get_email_body(msg)
        
        print(f"Email parsed - Subject: {subject}, From: {sender_email}")
        
        # Check if email matches internship keywords
        if not is_internship_email(subject, body, sender_email):
            print("Email does not match internship keywords.  Skipping.")
            return {
                'statusCode': 200,
                'body': json.dumps('Email filtered out - not internship related')
            }
        
        # Extract company and position
        company = extract_company(from_email, sender_email, body)
        position = extract_position(subject, body)
        
        # Extract URLs from email body
        urls = extract_urls(body)
        application_url = urls[0] if urls else ""
        
        # Parse email date
        email_received_date = parse_email_date(date_str)
        
        # Create entry in Notion
        create_notion_entry(
            position=position,
            company=company,
            sender_email=sender_email,
            subject=subject,
            email_received_date=email_received_date,
            application_url=application_url,
            body_snippet=body[: 500]  # First 500 chars
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps('Successfully processed email and added to Notion')
        }
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'statusCode': 500,
            'body': json. dumps(f'Error:  {str(e)}')
        }

def extract_email_address(from_field):
    """Extract email address from 'From' field"""
    # Handle formats like: "Company Name <email@example.com>" or "email@example.com"
    match = re.search(r'<(. +?)>', from_field)
    if match:
        return match.group(1)
    
    # If no angle brackets, try to find email pattern
    match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_field)
    if match:
        return match.group(0)
    
    return from_field

def get_email_body(msg):
    """Extract email body (prefer plain text over HTML)"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            
            # Skip attachments
            if "attachment" in content_disposition: 
                continue
            
            if content_type == "text/plain": 
                body = part.get_payload(decode=True).decode(errors='ignore')
                break
            elif content_type == "text/html" and not body:
                body = part.get_payload(decode=True).decode(errors='ignore')
    else:
        body = msg.get_payload(decode=True).decode(errors='ignore')
    
    return body

def is_internship_email(subject, body, sender):
    """Check if email is related to internship applications"""
    text_to_check = f"{subject} {body} {sender}".lower()
    
    for keyword in KEYWORDS:
        if keyword. lower() in text_to_check:
            print(f"Matched keyword: {keyword}")
            return True
    
    return False

def extract_company(from_field, sender_email, body):
    """Extract company name from email"""
    # Try to extract from "From" field (e.g., "Google Careers <noreply@google.com>")
    match = re.search(r'^([^<]+)', from_field)
    if match:
        company = match.group(1).strip()
        # Clean up common patterns
        company = re.sub(r'\s*(careers|talent|recruiting|hr|jobs)\s*', '', company, flags=re.IGNORECASE)
        if company and len(company) > 2:
            return company
    
    # Try to extract from email domain
    if '@' in sender_email:
        domain = sender_email.split('@')[1]
        # Remove common subdomains and TLD
        domain = re.sub(r'^(noreply|no-reply|careers|jobs|talent|hr|mail)\.', '', domain)
        domain = re.sub(r'\.(com|org|io|co|net)$', '', domain)
        return domain. capitalize()
    
    return "Unknown Company"

def extract_position(subject, body):
    """
    Extract position/role name from email subject and body.  
    Returns a string with the position name or a default.  
    """
    text = (subject or "") + "\n" + (body or "")
    
    # Safe pattern - explicit word boundary search for internship keywords
    pattern = r'\b(internship|intern|application|apply|position|role|opportunity)\b'
    
    # Debug:  log what we're searching
    print(f"DEBUG: searching pattern={repr(pattern)} in text={repr(text[: 200])}")
    
    try:
        match = re.search(pattern, text, re. IGNORECASE)
    except re.error as e:
        print(f"Regex error: {e}, pattern={repr(pattern)}")
        return "Internship Position"  # Default fallback
    
    if match:
        keyword = match.group()
        print(f"Matched keyword: {keyword}")
        
        # Use the subject line as the position if it exists and is reasonable length
        if subject and 5 < len(subject) < 150:
            # Clean the subject - remove common prefixes
            clean_subject = re.sub(r'^(re:|fwd? :|\[.*?\])\s*', '', subject, flags=re.IGNORECASE).strip()
            print(f"Using subject as position: {clean_subject}")
            return clean_subject
        
        # Fallback:  use generic title with matched keyword
        return f"{keyword. capitalize()} Position"
    
    # No match found - use subject or generic fallback
    if subject and len(subject) > 0:
        clean_subject = re.sub(r'^(re:|fwd?: |\[.*?\])\s*', '', subject, flags=re. IGNORECASE).strip()
        return clean_subject[: 150] if clean_subject else "Internship Application"
    
    return "Internship Application"

def extract_urls(text):
    """Extract URLs from email body"""
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, text)
    # Filter out tracking pixels and common non-application URLs
    filtered_urls = [url for url in urls if not any(x in url. lower() for x in ['unsubscribe', 'pixel', 'track', 'beacon'])]
    return filtered_urls[: 5]  # Return max 5 URLs

def parse_email_date(date_str):
    """Parse email date to ISO format"""
    try:
        if date_str: 
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            return dt.isoformat()
    except: 
        pass
    
    # Return current time if parsing fails
    return datetime.utcnow().isoformat()

def get_data_source_id(database_id):
    """Retrieve first data_source_id from database (assumes single-source)"""
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2025-09-03",  # Required
        "Content-Type": "application/json"
    }
    req = urllib.request.Request(
        f"https://api.notion.com/v1/databases/{database_id}",
        headers=headers
    )
    try:
        with urllib.request.urlopen(req) as response:
            db_info = json.loads(response.read().decode('utf-8'))
            data_sources = db_info.get('data_sources', [])
            if data_sources:
                print(f"Found data source: {data_sources[0]['id'][:8]}...")
                return data_sources[0]['id']  # Use first (typically only) source
            raise Exception("No data sources found")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        raise Exception(f"Database fetch failed: {error_body}")


def create_notion_entry(position, company, sender_email, subject, email_received_date, application_url, body_snippet):
    """Create a new entry in Notion database"""
    
    # Parse date to Notion format (YYYY-MM-DD)
    try:
        received_date = datetime.fromisoformat(email_received_date. replace('Z', '+00:00'))
        notion_date = received_date.strftime('%Y-%m-%d')
    except:
        notion_date = datetime.utcnow().strftime('%Y-%m-%d')
    
    # Construct Notion page properties
    properties = {
        "Position": {
            "title": [
                {
                    "text": {
                        "content": position[: 2000]  # Notion title limit
                    }
                }
            ]
        },
        "Company": {
            "rich_text": [
                {
                    "text": {
                        "content":  company[:2000]
                    }
                }
            ]
        },
        "Status": {
            "status": {
                "name": "Applied"
            }
        },
        "Submission Date": {
            "date": {
                "start": notion_date
            }
        },
        "Source Email": {
            "email": sender_email
        },
        "Last Updated": {
            "date": {
                "start": notion_date
            }
        }
    }
    
    # Add optional properties if they exist in your database
    # Uncomment these if you added these fields to your Notion database
    
    # if subject:
    #     properties["Email Subject"] = {
    #         "rich_text": [{
    #             "text": {"content": subject[:2000]}
    #         }]
    #     }
    
    # if email_received_date:
    #     properties["Email Received Date"] = {
    #         "date": {"start": notion_date}
    #     }
    
    # if application_url:
    #     properties["Application URL"] = {
    #         "url": application_url[: 2000]
    #     }
    
    print(f"DEBUG: Creating Notion entry with properties: {json.dumps(properties, indent=2)}")
    print(f"DEBUG: Getting datasource ID with DB_ID: {NOTION_DB_ID}")
    data_source_id = get_data_source_id(NOTION_DB_ID)

    data = {
        "parent": {"data_source_id": data_source_id},
        "properties":  properties
    }

    api_key = NOTION_API_KEY

    print(f"DEBUG: API key starts with: {api_key[:10]}...  ends with: ... {api_key[-4:]}")
    print(f"DEBUG: API key length: {len(api_key)}")
    print(f"DEBUG: Datasource ID: {NOTION_DB_ID}")
    
    # Make request to Notion API
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2025-09-03"
    }
    
    req = urllib.request.Request(
        NOTION_API_URL,
        data=json.dumps(data).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print(f"Successfully created Notion entry: {result. get('id')}")
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"Notion API error: {e.code} - {error_body}")
        raise Exception(f"Failed to create Notion entry: {error_body}")