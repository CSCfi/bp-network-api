import asynctest

from aioresponses import aioresponses
import aiohttp

from registry.utils.utils import http_request_info, parse_service_info, construct_json
from registry.utils.utils import query_params, db_get_service_urls, db_get_recaching_credentials
from registry.utils.utils import generate_service_key, generate_service_id

from .db_test_classes import Connection


class MockRequest:
    """Mock request for testing."""

    def __init__(self, service_type=None, api_version=None, service_id=None):
        """Initialise object."""
        self.query = {
            'type': service_type,
            'apiVersion': api_version
        }
        self.match_info = {
            'service_id': service_id
        }


class TestUtils(asynctest.TestCase):
    """Test registry utility functions."""

    @aioresponses()
    async def test_http_request_info_ok(self, m):
        """Test seccessful request of service info."""
        data = {'name': 'Best Beacon'}
        m.get('https://beacon.fi/service-info', status=200, payload=data)
        info = await http_request_info('https://beacon.fi/service-info')
        self.assertEqual({'name': 'Best Beacon'}, info)

    @aioresponses()
    async def test_http_request_info_fail(self, m):
        """Test failed request of service info."""
        m.get('https://beacon.fi/service-info', status=400)
        with self.assertRaises(aiohttp.web_exceptions.HTTPInternalServerError):
            await http_request_info('https://beacon.fi/service-info')

    async def test_parse_service_info_ga4gh(self):
        """Test parsing of service info in GA4GH format."""
        service_id = 'fi.beacon'
        service_info = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'type': 'org.ga4gh:beacon:1.0.0',
            'description': 'Finnish Data',
            'organization': {
                'name': 'CSC',
                'url': 'https://csc.fi/'
            },
            'contactUrl': 'https://csc.fi/contact',
            'documentationUrl': 'https://beacon.fi/docs',
            'createdAt': '2019-09-01T12:00:00Z',
            'updatedAt': '2019-09-01T12:00:00Z',
            'environment': 'prod',
            'version': '1.0.0'
        }
        request = {'url': 'https://beacon.fi/service-info'}
        parsed_info = await parse_service_info(service_id, service_info, request)
        expected_info = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'type': 'org.ga4gh:beacon',
            'description': 'Finnish Data',
            'url': 'https://beacon.fi/service-info',
            'contact_url': 'https://csc.fi/contact',
            'api_version': '1.0.0',
            'service_version': '1.0.0',
            'environment': 'prod',
            'organization': 'CSC',
            'organization_url': 'https://csc.fi/',
            'organization_logo': None
        }
        self.assertEqual(parsed_info, expected_info)

    async def test_parse_service_info_beacon(self):
        """Test parsing of service info in Beacon API format."""
        service_id = 'fi.beacon'
        service_info = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'description': 'Finnish Data',
            'organization': {
                'name': 'CSC',
                'welcomeUrl': 'https://csc.fi/',
                'contactUrl': 'https://csc.fi/contact',
                'logoUrl': 'https://csc.fi/logo.png'
            },
            'apiVersion': '1.0.0',
            'version': '1.0.0'
        }
        request = {'url': 'https://beacon.fi/'}
        parsed_info = await parse_service_info(service_id, service_info, request)
        expected_info = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'type': 'org.ga4gh:beacon',
            'description': 'Finnish Data',
            'url': 'https://beacon.fi/',
            'contact_url': 'https://csc.fi/contact',
            'api_version': '1.0.0',
            'service_version': '1.0.0',
            'environment': 'prod',
            'organization': 'CSC',
            'organization_url': 'https://csc.fi/',
            'organization_logo': 'https://csc.fi/logo.png'
        }
        self.assertEqual(parsed_info, expected_info)

    async def test_construct_json(self):
        """Test JSON construction from database record."""
        data = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'type': 'org.ga4gh:beacon',
            'api_version': '1.0.0',
            'description': 'Finnish Data',
            'organization': 'CSC',
            'organization_url': 'https://csc.fi/',
            'organization_logo': 'https://csc.fi/logo.png',
            'contact_url': 'https://csc.fi/contact',
            'created_at': '2019-09-01T12:00:00Z',
            'updated_at': '2019-09-01T12:00:00Z',
            'environment': 'prod',
            'service_version': '1.0.0',
            'url': 'https://beacon.fi/'
        }
        constructed_format = await construct_json(data)
        expected_format = {
            'id': 'fi.beacon',
            'name': 'Finnish Beacon',
            'type': 'org.ga4gh:beacon:1.0.0',
            'description': 'Finnish Data',
            'organization': {
                'name': 'CSC',
                'url': 'https://csc.fi/',
                'logoUrl': 'https://csc.fi/logo.png'
            },
            'contactUrl': 'https://csc.fi/contact',
            'createdAt': '2019-09-01T12:00:00Z',
            'updatedAt': '2019-09-01T12:00:00Z',
            'environment': 'prod',
            'version': '1.0.0',
            'url': 'https://beacon.fi/'
        }
        self.assertEqual(constructed_format, expected_format)

    async def test_query_params_all(self):
        """Test parsing of path query params."""
        request = MockRequest(service_type='org.ga4gh:beacon',
                              api_version='1.0.0',
                              service_id='fi.beacon')
        service_id, params = await query_params(request)
        self.assertEqual(service_id, 'fi.beacon')
        self.assertEqual(params, {'type': 'org.ga4gh:beacon',
                                  'apiVersion': '1.0.0'})

    async def test_query_params_none(self):
        """Test parsing of path query params."""
        request = MockRequest()
        service_id, params = await query_params(request)
        self.assertEqual(service_id, None)
        self.assertEqual(params, {'type': None, 'apiVersion': None})

    async def test_get_service_urls_found(self):
        """Test retrieval of service urls: urls found."""
        connection = Connection(return_value=[{'service_url': 'https://beacon1.fi/'},
                                              {'service_url': 'https://beacon2.fi/'}])
        service_urls = await db_get_service_urls(connection, service_type='org.ga4gh:beacon')
        self.assertEqual(len(service_urls), 2)

    async def test_get_service_urls_none(self):
        """Test retrieval of service urls: none found."""
        connection = Connection(return_value=[])
        service_urls = await db_get_service_urls(connection, service_type='org.ga4gh:beacon')
        self.assertEqual(len(service_urls), 0)

    async def test_get_recaching_credentials_found(self):
        """Test retrieval of recaching credentials: creds found."""
        connection = Connection(return_value=[{'url': 'https://beacon1.fi', 'service_key': 'abc123'},
                                              {'url': 'https://beacon1.fi', 'service_key': 'abc123'}])
        credentials = await db_get_recaching_credentials(connection)
        self.assertEqual(len(credentials), 2)

    async def test_get_recaching_credentials_none(self):
        """Test retrieval of recaching credentials: none found."""
        connection = Connection(return_value=[])
        credentials = await db_get_recaching_credentials(connection)
        self.assertEqual(len(credentials), 0)

    async def test_generate_service_key(self):
        """Test generation of service key."""
        key = await generate_service_key()
        self.assertEqual(type(key), str)
        self.assertEqual(len(key), 86)

    async def test_generate_service_id(self):
        """Test generation of service id."""
        id1 = await generate_service_id('https://beacon.fi/')
        self.assertEqual(id1, 'fi.beacon')
        id2 = await generate_service_id('https://beacon.fi/endpoint')
        self.assertEqual(id2, 'fi.beacon')
        id3 = await generate_service_id('beacon.fi/endpoint')
        self.assertEqual(id3, 'fi.beacon')


if __name__ == '__main__':
    asynctest.main()
