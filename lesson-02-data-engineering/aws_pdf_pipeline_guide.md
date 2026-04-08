# AWS Pipeline — PDF Ingestion

This guide will walk you through setting up an automated pipeline on AWS to process PDF documents.
**Architecture:** `PDF (pypdf) -> S3 -> SQS -> Lambda -> S3`

## Prerequisites
- An AWS account with admin permissions.
- Python 3.10+ installed locally (for optional local zip packaging).

---

## Step 1: Create S3 Buckets
We need two logical buckets: an **Input Bucket** and an **Output Bucket**.

1. Go to the **S3** service in the AWS Management Console.
2. Click **Create bucket**.
3. Name your first bucket: `pdf-ingestion-input-[your-initials]`.
4. Click **Create bucket**.
5. Repeat the process to create a second bucket: `pdf-ingestion-output-[your-initials]`.

---

## Step 2: Create an SQS Queue
1. Go to the **SQS (Simple Queue Service)** in the AWS Management Console.
2. Click **Create queue**.
3. Choose **Standard** queue.
4. Name your queue: `pdf-ingestion-queue`.
5. Under **Access policy**, select **Advanced**, and set the policy to allow S3 to send messages to this queue. *Replace the placeholders with your actual Queue ARN, Bucket ARN, and Account ID:*
   ```json
   {
     "Version": "2012-10-17",
     "Id": "example-ID",
     "Statement": [
       {
         "Sid": "example-statement-ID",
         "Effect": "Allow",
         "Principal": {
           "Service": "s3.amazonaws.com"
         },
         "Action": "SQS:SendMessage",
         "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:pdf-ingestion-queue",
         "Condition": {
           "StringEquals": {
             "aws:SourceAccount": "ACCOUNT_ID"
           },
           "ArnLike": {
             "aws:SourceArn": "arn:aws:s3:::pdf-ingestion-input-*"
           }
         }
       }
     ]
   }
   ```
6. Click **Create queue**.

---

## Step 3: Trigger SQS from S3
1. Go back to your input bucket `pdf-ingestion-input-[your-initials]` in S3.
2. Go to the **Properties** tab.
3. Scroll down to **Event notifications** and click **Create event notification**.
4. Name: `PdfUploadEvent`.
5. Select **All object create events** (`s3:ObjectCreated:*`).
6. Filter by suffix: `.pdf`.
7. Scroll down to **Destination**, choose **SQS queue**, and select `pdf-ingestion-queue`.
8. Click **Save changes**.

---

## Step 4: Create the Lambda Function

### 4.1 Write the Lambda Code (`lambda_function.py`)

Create a local directory or just paste this code into the AWS console once you create the Lambda:

```python
import json
import boto3
import urllib.parse
from io import BytesIO
from pypdf import PdfReader

s3 = boto3.client('s3')
OUTPUT_BUCKET = "pdf-ingestion-output-[your-initials]" # Update this!

def lambda_handler(event, context):
    for record in event['Records']:
        # SQS sends the message in the 'body' string
        sqs_body = json.loads(record['body'])
        
        # When triggered from S3 directly to SQS, SQS 'body' contains S3 records
        if 'Records' not in sqs_body:
            continue
            
        for s3_record in sqs_body['Records']:
            source_bucket = s3_record['s3']['bucket']['name']
            file_key = urllib.parse.unquote_plus(s3_record['s3']['object']['key'], encoding='utf-8')
            
            try:
                # 1. Download the PDF from S3
                response = s3.get_object(Bucket=source_bucket, Key=file_key)
                pdf_content = response['Body'].read()
                
                # 2. Extract text using pypdf
                pdf_file = BytesIO(pdf_content)
                reader = PdfReader(pdf_file)
                
                extracted_text = ""
                for page in reader.pages:
                    extracted_text += page.extract_text() + "\n"
                
                # 3. Save the result back to the Output S3 Bucket
                output_key = file_key.replace('.pdf', '.txt')
                s3.put_object(
                    Bucket=OUTPUT_BUCKET,
                    Key=output_key,
                    Body=extracted_text.encode('utf-8')
                )
                
                # OPTIONAL Cleanup immediately (as requested in homework)
                try:
                    s3.delete_object(Bucket=source_bucket, Key=file_key)
                    print(f"Deleted source file {file_key} from {source_bucket}")
                except Exception as e:
                    print(f"Failed to delete {file_key}: {e}")
                
                print(f"Successfully processed {file_key}")
                
            except Exception as e:
                print(f"Error processing {file_key} from bucket {source_bucket}: {e}")
                raise e
```

### 4.2 Create the Lambda in Console
1. Go to **AWS Lambda**.
2. Click **Create function** -> **Author from scratch**.
3. Name: `pdf-processor`.
4. Runtime: **Python 3.10**.
5. Click **Create function**.
6. **Important Permissions:** Go to the Configuration tab -> **Permissions** -> click the role name. Attach the policy `AmazonS3FullAccess` and `AWSLambdaSQSQueueExecutionRole` to the Lambda execution role.

### 4.3 Add Trigger & Dependencies
1. Under **Configuration -> Triggers**, add an **SQS** trigger. Select your `pdf-ingestion-queue`.
2. Since `pypdf` is a third-party library, you will need to upload a **Layer** or zipped deployment package containing the library. (You can create this by running `pip install pypdf -t .` in a temp folder, creating a `zip`, and uploading it).

---

## Step 5: S3 File Cleanup (Crucial constraint)
The task specifies: *"Delete all uploaded documents from S3 - they pull the budget even at rest"*. 

There are two approaches to do this:
1. **Immediate deletion** via the Lambda function (I added `s3.delete_object` directly in the script). 
2. **Lifecycle rules** in S3 (e.g., delete objects after 1 day). To set this: go to S3 Bucket -> **Management** tab -> **Lifecycle rules** -> **Create lifecycle rule** -> Apply to all objects -> select **Expire current versions of objects** -> Set days to 1. 

---

## Step 6: Setting a Budget Limit in AWS

To avoid unexpected charges:

1. Search for and open **AWS Billing** (or **AWS Billing and Cost Management**).
2. On the left sidebar, click **Budgets** (Billing -> Budgets).
3. Click **Create budget**.
4. Choose **Use a template (simplified)** and select **Zero spend budget**.
5. Enter an email address to receive alerts.
6. Click **Create budget**. You will now receive an email the moment your monthly AWS cost exceeds $00.01!
