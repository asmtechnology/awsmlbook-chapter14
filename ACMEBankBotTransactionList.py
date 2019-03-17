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
    
# this function returns True if the specified customer_identifier
# and account_identifier combination exists in the ACMEBankAccount table.
def validate_account_identifier(customer_identifier, account_identifier):
    
    account_table = dynamodb_resource.Table('ACMEBankAccount')
    
    dynamodb_response = account_table.query(
        KeyConditionExpression = Key('CustomerIdentifier').eq(customer_identifier) & Key('AccountIdentifier').eq(account_identifier)
    )
    
    if dynamodb_response['Count'] == 0:
        return False
        
    return True

# this function returns a string that contains information
# on the transactions in the specified account. 
def get_transaction_summary(account_identifier):
    
    transaction_table = dynamodb_resource.Table('ACMEAccountTransaction')
    
    dynamodb_response = transaction_table.query(
        KeyConditionExpression = Key('AccountIdentifier').eq(account_identifier)
    )
    
    num_transactions = dynamodb_response['Count'] 
    if num_transactions == 0:
        return 'I could not find any transactions for this account on our systems. Is there anything else I can help you with?'
        
    response_string = ''
    transaction_array = dynamodb_response['Items'] 
    for i in range(num_transactions):
        transaction_object = transaction_array[i]

        transaction_number = transaction_object['TransactionIdentifier']
        transaction_amount = transaction_object['Amount']
        transaction_date = transaction_object['Date']
        transaction_type_code = transaction_object['Type']

        transaction_type_description = 'credit'
        if transaction_type_code == 'CW':
            transaction_type_description = 'cash withdrawal'
        elif transaction_type_code == 'TFR':
            transaction_type_description = 'outbound transfer'

        transaction_description = 'Transaction #{0}: {1} of £{2} on {3}'.format(transaction_number,  
                                    transaction_type_description, 
                                    transaction_amount, 
                                    transaction_date)
                                        
        response_string = response_string + transaction_description

        if i == num_transactions - 1:
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

    if intent_name != 'ViewTransactionList':
        raise Exception('This function can only be used with the ViewTransactionList intent')

    # get session attributes
    # session attributes are not used in this code, but it is possible to read and
    # modify values as needed.
    session_attributes = event['sessionAttributes'] 

    # get CustomerIdentifier slot
    intent_slots = event['currentIntent']['slots']
    customer_identifier = intent_slots["CustomerIdentifier"]
    account_identifier = intent_slots["AccountIdentifier"]

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
    
        # If the user has not provided a value for the 
        # AccountIdentifier slot, then return a response
        # that will result in the chatbot asking the user
        # to provide a value for the slot.
        if account_identifier is None:
            return elicit_slot('AccountIdentifier',
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
    
        # validate AccountIdentifier slot.
        # if it is invalid, then ask the customer to
        # provide a value.
        if not validate_account_identifier(customer_identifier, account_identifier):
            
            # set the invalid intent slot to None so that
            # the chatbot knows that the slot does not have 
            # a value.
            intent_slots['AccountIdentifier'] = None
            
            return defer_next_action_to_chatbot(session_attributes, 
                                intent_slots)


    # read a list of transactions for the account
    # from DynamoDB table ACMEAccountTransaction and 
    # return a JSON object with account details.
    
    transaction_summary = get_transaction_summary(account_identifier)
    
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState' : 'Fulfilled',
            'message': {
                'contentType': 'PlainText',
                'content': transaction_summary
            }
        }
    }

