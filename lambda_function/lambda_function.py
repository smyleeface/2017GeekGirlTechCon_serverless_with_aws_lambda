from datetime import datetime
import json
import logging
import os

import boto3

# logging setup
logging.basicConfig()
logging.Logger('lambda_upload')
logger = logging.getLogger('lambda_upload')
logger.setLevel(logging.INFO)

# clients
session = boto3.Session()
sns_client = session.client('sns')
s3_client = session.client('s3')
rek_client = session.client('rekognition')

# lookup sns topic arn
all_topics = sns_client.list_topics()
for topics in all_topics['Topics']:
    if topics['TopicArn'].endswith(os.environ['TOPIC_NAME']):
        topic_arn = topics['TopicArn']


def get_faces_info(s3_object):
    """Gets information about the face and pixels around the face.

    :param s3_object: dict
    :return: string
    """
    email = "\nFace Info\n\n"
    responses = rek_client.detect_faces(
        Image=s3_object,
        Attributes=['ALL']
    )
    logger.info("Running detect face Rekognition...")
    for response in responses['FaceDetails']:
        for type in response:
            value = response[type]
            email += "{0}: {1}\n".format(type, value)

    return email


def get_label_confidence(s3_object):
    """Gets the labels and the confidence level.

    :param s3_object: dict
    :return: string
    """
    email = "\nLabel Confidence:\n\n"
    responses = rek_client.detect_labels(
        Image=s3_object
    )
    logger.info("Running detect label Rekognition...")
    for response in responses['Labels']:
        email += "{0}: {1}%\n".format(response['Name'], round(response['Confidence'], 2))

    return email


def lambda_handler(event, context):
    """
    The main function. This will run after initializing everything outside this method.

    :param event:
    :param context:
    :return:
    """
    # print the event and context info
    logger.info(json.dumps(event))
    logger.info(vars(context))

    # gather the info we need
    upload_event = event['Records'][0]
    region = upload_event['awsRegion']
    bucket = upload_event['s3']['bucket']['name']
    key = upload_event['s3']['object']['key']
    s3_upload_url = "https://s3-{0}.amazonaws.com/{1}/{2}".format(region, bucket, key)
    s3_object = {
        'S3Object': {
            'Bucket': bucket,
            'Name': key
        }
    }

    # get the email content
    email = '{0}\n'.format(s3_upload_url)
    email += get_label_confidence(s3_object)
    email += get_faces_info(s3_object)

    # create message content
    subject = '{:%Y%m%d%H%M%S}'.format(datetime.now())
    message = {
        "default": "Finished scanning image.",
        "email": email,
        "sms": "Finished scanning image: {0}".format(s3_upload_url)
    }
    message_json = json.dumps(message)

    # send message
    logger.info("Sending notifications")
    sns_client.publish(
        TopicArn=topic_arn,
        Message=message_json,
        MessageStructure='json',
        Subject='{0}: Finished scanning image'.format(subject)
    )
    return "done"
