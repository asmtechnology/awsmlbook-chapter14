import json
import boto3
import logging
import os
import sys
from boto3.dynamodb.conditions import Key, Attr

# create and configure a logger object.
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# create an object that can be used to access Amazon DynamoDB tables
# in the same region as this AWS Lambda function.
dynamodb_resource = boto3.resource('dynamodb')

# this function returns a JSON object which when sent to Amaxon Lex
# will result in the chatbot asking the end user to provide the value
# of the slot specified in 'slot_to_elicit'
def elicit_slot(slot_to_elicit, session_attributes, intent_name, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit
        }
    }

# this function returns a JSON object which when sent to Amaxon Lex
# will result in the chatbot determining the next course of action.
def defer_next_action_to_chatbot(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

# this function returns True if the specified customer_identifier
# exists in the ACMEBankCustomer table.
def validate_customer_identifier(customer_identifier):
    
    customer_table = dynamodb_resource.Table('ACMEBankCustomer')
    
    dynamodb_response = customer_table.query(
        KeyConditionExpression = Key('CustomerIdentifier').eq(customer_identifier)
    )
    
    if dynamodb_response['Count'] == 0:
        return False
        
    return True
    

# this function returns a string that contains information
# on the accounts held by the customer and the balances in
# those accounts.
def get_account_overview(customer_identifier):
    
    account_table = dynamodb_resource.Table('ACMEBankAccount')
    
    dynamodb_response = account_table.query(
        KeyConditionExpression = Key('CustomerIdentifier').eq(customer_identifier)
    )
    
    num_accounts = dynamodb_response['Count'] 
    if num_accounts == 0:
        return 'I could not find any accounts for you on our systems. Is there anything else I can help you with?'
        
    response_string = ''
    account_array = dynamodb_response['Items'] 
    for i in range(num_accounts):
        account_object = account_array[i]
        account_description = 'The balance in account number {0} is £{1}'.format(account_object['AccountIdentifier'], account_object['AccountBalance'])
        response_string = response_string + account_description

        if i == num_accounts - 1:
            response_string = response_string + ". Is there anything else I can help you with?" 
        else:
            response_string = response_string + ", " 

    return response_string
    

def lambda_handler(event, context):
    
    # log the event to the CloudWatch log group associated
    # with this AWSLambda function. 
    logger.debug(event)
    
    # name of the bot that is executing this function
    bot_name = event['bot']['name']

    # name of the intent that has executed this function.
    intent_name = event['currentIntent']['name']

    # ensure this lambda function is not being called by
    # the wrong bot/intent.
    if bot_name != 'ACMEBankBot':
        raise Exception('This function can only be used with the ACMEBankBot')

    if intent_name != 'AccountOverview':
        raise Exception('This function can only be used with the AccountOverview intent')

    # get session attributes
    # session attributes are not used in this code, but it is possible to read and
    # modify values as needed.
    session_attributes = event['sessionAttributes'] 

    # get CustomerIdentifier slot
    intent_slots = event['currentIntent']['slots']
    customer_identifier = intent_slots["CustomerIdentifier"]

    # is this function being executed for validation or fulfillment?
    invocation_source = event['invocationSource']
    
    # initialization and validation
    if invocation_source == 'DialogCodeHook':

        # If the user has not provided a value for the 
        # CustomerIdentifier slot, then return a response
        # that will result in the chatbot asking the user
        # to provide a value for the slot.
        if customer_identifier is None:
            return elicit_slot('CustomerIdentifier',
                                session_attributes,
                                intent_name,
                                intent_slots)
    
    
        # validate CustomerIdentifier slot.
        # if it is invalid, then ask the customer to
        # provide a value.
        if not validate_customer_identifier(customer_identifier):
            
            # set the invalid intent slot to None so that
            # the chatbot knows that the slot does not have 
            # a value.
            intent_slots['CustomerIdentifier'] = None
            
            return defer_next_action_to_chatbot(session_attributes, 
                                intent_slots)


    # read a list of accounts for the customer
    # from DynamoDB table ACMEBankAccounts and 
    # return a JSON object with account details.
    
    account_overview = get_account_overview(customer_identifier)
    
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState' : 'Fulfilled',
            'message': {
                'contentType': 'PlainText',
                'content': account_overview
            }
        }
    }

