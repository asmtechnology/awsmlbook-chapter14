import json
import boto3
import logging
import os
import sys

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message
        }
    }

def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

def build_validation_result(is_valid, violated_slot, message_content):
    if message_content is None:
        return {
            "isValid": is_valid,
            "violatedSlot": violated_slot,
        }

    return {
        'isValid': is_valid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def validate_customer_identifier(customer_identifier):
   
    if len(customer_identifier) == 0:
        return build_validation_result(False, 
                                       'CustomerIdentifier',
                                       'The customer identifier you have provided is invalid. Please try again.')

    if customer_identifier != 'CUS01' and customer_identifier != 'CUS02':
        return build_validation_result(False, 
                                       'CustomerIdentifier',
                                       'The customer identifier you have provided is invalid. Please try again.')

    return build_validation_result(True, None, None)


# --- Main handler ---

def lambda_handler(event, context):
    # name of the bot that is executing this function
    bot_name = event['bot']['name']
    logger.debug('event.bot.name={}'.format(bot_name))

    # name of the intent that has executed this function.
    intent_name = event['currentIntent']['name']
    logger.debug('intent.name={}'.format(intent_name))

    #ensure bot_name and intent_name have expected values
    if bot_name != 'ACMEBankBot' and intent_name != 'AccountOverviewIntent':
        raise Exception('Intent ' + intent_name + ' not supported.')
    
    # get slots
    intent_slots = event['currentIntent']['slots']
    customer_identifier = intent_slots["CustomerIdentifier"]

    logger.debug('intent.slots={}'.format(intent_slots))
    logger.debug('slot.customer_identifier={}'.format(customer_identifier)

    # get session attributes
    # session attributes are not used in this code, but it is possible to read and
    # modify values as needed.
    session_attributes = event['sessionAttributes'] 
    if session_attributes is None:
       session_attributes = {}

    logger.debug('sessionAttributes={}'.format(session_attributes)

    validation_result = validate_customer_identifier(customer_identifier)
    if not validation_result['isValid']:
        intent_slots[validation_result['violatedSlot']] = None
        return elicit_slot(session_attributes,
                            intent_name,
                            intent_slots,
                            validation_result['violatedSlot'],
                            validation_result['message'])


    return delegate(output_session_attributes, intent_slots)
