"""Explicit local Sandbox Orders test utility. Never accepts a live API URL."""
import argparse
import json
import os
import re
from urllib.parse import urlparse
from uuid import UUID
from backend.integrations.paypal import SandboxClient
from backend.app.errors import APIError


def order_id(value):
    if not re.fullmatch(r'[A-Z0-9]{5,40}',value):
        raise ValueError('Supply the Sandbox order ID returned by create.')
    return value


def result(data):
    """Print only order/capture IDs and status; never payer data or tokens."""
    if not isinstance(data,dict) or not isinstance(data.get('id'),str) or not isinstance(data.get('status'),str):
        raise APIError(503,'PAYPAL_UNAVAILABLE','Invalid Sandbox order response.')
    value={'environment':'sandbox','order_id':order_id(data['id']),'status':data['status']}
    captures=[]
    for unit in data.get('purchase_units',[]):
        for capture in unit.get('payments',{}).get('captures',[]):
            captures.append({'id':capture.get('id'),'status':capture.get('status')})
    value['captures']=captures
    for link in data.get('links',[]):
        if link.get('rel') in ('approve','payer-action'):
            url=link.get('href',''); parsed=urlparse(url)
            if parsed.scheme!='https' or parsed.netloc!='www.sandbox.paypal.com':
                raise APIError(503,'PAYPAL_UNAVAILABLE','Invalid Sandbox approval URL.')
            value['approval_url']=url
    return value


def create(client,request_id,return_url):
    key=str(UUID(request_id))
    parsed=urlparse(return_url)
    if parsed.scheme!='http' or parsed.hostname not in ('localhost','127.0.0.1') or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Return URL must be a plain local HTTP URL without credentials, query or fragment.')
    data=client.authorized('POST','/v2/checkout/orders',required_scope=None,headers={'PayPal-Request-Id':key,'Prefer':'return=representation'},json={
        'intent':'CAPTURE',
        'purchase_units':[{'description':'ProofPay synthetic Sandbox test only','amount':{'currency_code':'USD','value':'1.00'}}],
        'payment_source':{'paypal':{'experience_context':{'shipping_preference':'NO_SHIPPING','user_action':'PAY_NOW','return_url':return_url,'cancel_url':return_url}}}
    })
    return result(data)


def capture(client,identifier,request_id):
    key=str(UUID(request_id))
    return result(client.authorized('POST','/v2/checkout/orders/'+order_id(identifier)+'/capture',required_scope=None,headers={'PayPal-Request-Id':key,'Prefer':'return=representation'},json={}))


def main():
    parser=argparse.ArgumentParser(description='Sandbox-only USD 1.00 payment testing; no live endpoints.')
    parser.add_argument('command',choices=['check','create','status','capture'])
    parser.add_argument('--order-id')
    parser.add_argument('--request-id',help='Persist and reuse this UUID for retries of the same create/capture operation.')
    parser.add_argument('--return-url',default='http://127.0.0.1:3000/')
    args=parser.parse_args()
    client_id,secret=os.getenv('PAYPAL_CLIENT_ID'),os.getenv('PAYPAL_CLIENT_SECRET')
    if not client_id or not secret: parser.error('Export PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET locally; do not paste them into chat.')
    client=SandboxClient(client_id,secret)
    try:
        if args.command=='check': output=client.check()
        elif args.command=='create':
            if not args.request_id: parser.error('--request-id UUID is required')
            output=create(client,args.request_id,args.return_url)
        else:
            if not args.order_id: parser.error('--order-id is required')
            if args.command=='capture':
                if not args.request_id: parser.error('--request-id UUID is required')
                output=capture(client,args.order_id,args.request_id)
            else: output=result(client.authorized('GET','/v2/checkout/orders/'+order_id(args.order_id),required_scope=None))
        print(json.dumps(output,indent=2))
    except APIError as exc:
        parser.exit(1,exc.code+': '+exc.message+'\n')
    except (ValueError,TypeError,AttributeError):
        parser.exit(1,'Invalid arguments or Sandbox response. No sensitive details displayed.\n')

if __name__=='__main__': main()
