import os
import json
import requests
import uuid
from util import get, omit
from json_schema import validate_schema
from db import DATABASE

BASE_URL = os.getenv('BASE_URL', 'http://localhost:5001')

list_url = f'{BASE_URL}/v1/urls'

with open('./swagger_meta_schema.json') as f:
    swagger_meta_schema = json.loads(f.read())

def uuid_hex():
    return uuid.uuid4().hex

def first(the_iterable, condition = lambda x: True):
    for i in the_iterable:
        if condition(i):
            return i

def get_valid_doc():
    return {'url': f'https://www.google.com?uuid={uuid_hex()}'}

def test_crud():
    # Get swagger spec
    response = requests.get(f'{BASE_URL}/v1/swagger.json')
    assert response.status_code == 200
    swagger = response.json()
    assert validate_schema(swagger, swagger_meta_schema) == None
    get_schema = get(swagger, 'paths./v1/urls/{id}.get.responses.200.content.application/json.schema')
    list_schema = get(swagger, 'paths./v1/urls.get.responses.200.content.application/json.schema')

    doc = get_valid_doc()

    # Create with invalid schema
    invalid_doc = {**doc, 'foo': 1}
    response = requests.post(list_url, json=invalid_doc)
    assert response.status_code == 400
    assert get(response.json(), 'error.message')

    # Successful create
    response = requests.post(list_url, json=doc)
    print(response.json())
    assert response.status_code == 200
    assert validate_schema(response.json(), get_schema) == None
    assert response.json()['url'] == doc['url']
    assert response.json()['id']
    assert response.json()['created_at']
    doc['id'] = response.json()['id']

    get_url = f'{list_url}/{doc["id"]}'

    # Verify create with get
    response = requests.get(get_url)
    assert response.status_code == 200
    assert validate_schema(response.json(), get_schema) == None
    assert response.json()['id'] == doc['id']
    assert response.json()['url'] == doc['url']

    # Get 404
    missing_id = 12345 if DATABASE == 'pg' else '5f299b3e9cd7d821d2b898c1'
    get_url_404 = f'{list_url}/{missing_id}'
    response = requests.get(get_url_404)
    assert response.status_code == 404

    # Get invalid id
    response = requests.get(f'{list_url}/fooobar')
    assert response.status_code == 400
    assert get(response.json(), 'error.message')

    if DATABASE == 'pg':
        # Create with url that already exists
        response = requests.post(list_url, json={'url': doc['url']})
        print(response.json())
        assert response.status_code == 400
        assert get(response.json(), 'error.message')

    # List
    response = requests.get(list_url)
    assert response.status_code == 200
    assert validate_schema(response.json(), list_schema) == None
    list_doc = first(response.json()['data'], lambda d: d['id'] == doc['id'])
    assert list_doc['url'] == doc['url']

    new_url = f'https://www.facebook.com?uuid={uuid_hex()}'

    # Update 404
    response = requests.put(get_url_404, json={'url': new_url})
    assert response.status_code == 404

    # Update with invalid schema
    response = requests.put(get_url, json={'url': 123})
    assert response.status_code == 400
    assert get(response.json(), 'error.message')

    # Successful update
    response = requests.put(get_url, json={'url': new_url})
    assert response.status_code == 200
    assert validate_schema(response.json(), get_schema) == None

    # Verify update with get
    response = requests.get(get_url)
    assert response.status_code == 200
    assert validate_schema(response.json(), get_schema) == None
    assert response.json()['url'] == new_url
    assert response.json()['updated_at']

    # Delete 404
    response = requests.delete(get_url_404)
    assert response.status_code == 404

    # Successful delete
    response = requests.delete(get_url)
    assert response.status_code == 200
    assert validate_schema(response.json(), get_schema) == None

    # Verify delete with get 404
    response = requests.get(get_url)
    assert response.status_code == 404

def test_update_full_doc():
    # Successful create
    doc = get_valid_doc()
    response = requests.post(list_url, json=doc)
    assert response.status_code == 200
    doc['id'] = response.json()['id']
    get_url = f'{list_url}/{doc["id"]}'

    # Successful get
    response = requests.get(get_url)
    assert response.status_code == 200
    doc = response.json()

    # Invalid update
    invalid_doc = {**doc, 'foo': 'bar'}
    response = requests.put(get_url, json=invalid_doc)
    assert response.status_code == 400

    # Empty update
    response = requests.put(get_url)
    assert response.status_code == 400

    # Successful update with full doc
    valid_doc = {**doc, 'url': f'https://www.facebook.com?uuid={uuid_hex()}'}
    response = requests.put(get_url, json=valid_doc)
    assert response.status_code == 200

    # Verify update with get
    response = requests.get(get_url)
    assert response.status_code == 200
    assert response.json()['updated_at']
    assert omit(response.json(), ['updated_at']) == valid_doc

    # Successful delete
    response = requests.delete(get_url)
    assert response.status_code == 200

def test_missing_path():
    response = requests.get(f'{BASE_URL}/fooooooobar')
    assert response.status_code == 404

def test_method_not_allowed():
    response = requests.put(f'{BASE_URL}/v1/urls')
    assert response.status_code == 405

def test_create_empty():
    response = requests.post(list_url)
    assert response.status_code == 400

def test_invalid_json_data():
    invalid_json = 'foo: bar'
    response = requests.post(list_url, data=invalid_json)
    assert response.status_code == 400

def test_create_invalid_url():
    doc = get_valid_doc()

    invalid_doc = {**doc, 'url': 'foobar'}
    response = requests.post(list_url, json=invalid_doc)
    assert response.status_code == 400

    invalid_doc = {**doc, 'url': f'https://www.example.com/foooobar'}
    response = requests.post(list_url, json=invalid_doc)
    print(response.json())
    assert response.status_code == 400

def test_parameter_validation():
    articles_url = f'{BASE_URL}/v1/articles'
    # Invalid header param
    response = requests.get(articles_url, headers={'Authorization': 's'})
    assert response.status_code == 400

    # Valid header param
    response = requests.get(articles_url, headers={'Authorization': 'secret'})
    assert response.status_code == 200

    # Invalid query param
    response = requests.get(articles_url, params={'q': 's'})
    assert response.status_code == 400

    # Valid query param
    response = requests.get(articles_url, params={'q': 'corona'})
    assert response.status_code == 200

def test_request_schema_validation():
    articles_url = f'{BASE_URL}/v1/articles'

    # Invalid schema
    response = requests.post(articles_url, json={'title': 123})
    assert response.status_code == 400

    # Valid schema
    response = requests.post(articles_url, json={'title': 'foobar'})
    assert response.status_code == 200

def test_response_headers():
    urls = [
        f'{BASE_URL}/v1/decorators_example',
        f'{BASE_URL}/v1/composed_decorators_example1',
        f'{BASE_URL}/v1/composed_decorators_example2'
    ]
    for url in urls:
        response = requests.get(url)
        assert response.status_code == 200
        assert response.headers.get('Cache-Control') == 'max-age=120'
        assert response.headers.get('X-Response-Time')
