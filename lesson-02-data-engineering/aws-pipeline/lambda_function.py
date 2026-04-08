import json
import boto3
import urllib.parse
from io import BytesIO
from pypdf import PdfReader

s3 = boto3.client('s3')
OUTPUT_BUCKET = "pdf-output-bucket-vs"


def lambda_handler(event, context):
    """
    AWS Lambda function triggered by SQS messages from S3 events.

    Pipeline: PDF uploaded to S3 -> S3 event -> SQS -> Lambda -> extracted text saved to S3
    """
    for record in event['Records']:
        # SQS sends the S3 event inside the 'body' field as a JSON string
        sqs_body = json.loads(record['body'])

        if 'Records' not in sqs_body:
            continue

        for s3_record in sqs_body['Records']:
            source_bucket = s3_record['s3']['bucket']['name']
            file_key = urllib.parse.unquote_plus(
                s3_record['s3']['object']['key'], encoding='utf-8'
            )

            try:
                # 1. Download the PDF from the input S3 bucket
                response = s3.get_object(Bucket=source_bucket, Key=file_key)
                pdf_content = response['Body'].read()

                # 2. Extract text from PDF using pypdf
                reader = PdfReader(BytesIO(pdf_content))
                extracted_text = ""
                for page in reader.pages:
                    extracted_text += page.extract_text() + "\n"

                # 3. Save extracted text to the output S3 bucket
                output_key = file_key.replace('.pdf', '.txt')
                s3.put_object(
                    Bucket=OUTPUT_BUCKET,
                    Key=output_key,
                    Body=extracted_text.encode('utf-8')
                )
                print(f"Saved extracted text to s3://{OUTPUT_BUCKET}/{output_key}")

                # 4. Delete the original PDF from the input bucket (cost saving)
                s3.delete_object(Bucket=source_bucket, Key=file_key)
                print(f"Deleted source file s3://{source_bucket}/{file_key}")

            except Exception as e:
                print(f"Error processing {file_key} from {source_bucket}: {e}")
                raise e
