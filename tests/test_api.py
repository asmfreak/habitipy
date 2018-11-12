import unittest
import tempfile
import os
from habitipy.api import parse_apidoc, ApiEndpoint

test_data = """
@api {post} /api/v3/user/webhook Create a new webhook - BETA
@apiParam (Body) {UUID} [id="Randomly Generated UUID"] The webhook's id
@apiParam (Body) {String} url The webhook's URL
@apiParam (Body) {String} [label] A label to remind you what this webhook does
@apiParam (Body) {Boolean} [enabled=true] If the webhook should be enabled
@apiParam (Body) {Sring="taskActivity","groupChatReceived"} [type="taskActivity"] The webhook's type.
@apiParam (Body) {Object} [options] The webhook's options. Wil differ depending on type. Required for `groupChatReceived` type. If a webhook supports options, the default values are displayed in the examples below
@apiSuccess (201) {Object} data The created webhook
@apiSuccess (201) {UUID} data.id The uuid of the webhook
@apiSuccess (201) {String} data.url The url of the webhook
@apiSuccess (201) {String} data.label A label for you to keep track of what this webhooks is for
@apiSuccess (201) {Boolean} data.enabled Whether the webhook should be sent
@apiSuccess (201) {String} data.type The type of the webhook
@apiSuccess (201) {Object} data.options The options for the webhook (See examples)
@api {put} /api/v3/user/webhook/:id Edit a webhook - BETA
@apiParam (Path) {UUID} id URL parameter - The id of the webhook to update
@apiParam (Body) {String} [url] The webhook's URL
@apiParam (Body) {String} [label] A label to remind you what this webhook does
@apiParam (Body) {Boolean} [enabled] If the webhook should be enabled
@apiParam (Body) {Sring="taskActivity","groupChatReceived"} [type] The webhook's type.
@apiParam (Body) {Object} [options] The webhook's options. Wil differ depending on type. The options are enumerated in the [add webhook examples](#api-Webhook-UserAddWebhook).
@apiSuccess {Object} data The updated webhook
@apiSuccess {UUID} data.id The uuid of the webhook
@apiSuccess {String} data.url The url of the webhook
@apiSuccess {String} data.label A label for you to keep track of what this webhooks is for
@apiSuccess {Boolean} data.enabled Whether the webhook should be sent
@apiSuccess {String} data.type The type of the webhook
@apiSuccess {Object} data.options The options for the webhook (See webhook add examples)
@api {delete} /api/v3/user/webhook/:id Delete a webhook - BETA
@apiParam (Path) {UUID} id The id of the webhook to delete
@apiParam (Query) [dueDate] type Optional date to use for computing the nextDue field for each returned task.
"""
wrong_apidoc_data = [
"""@api {delete} /api/v3/user/webhook/:id Delete a webhook - BETA
@apiParam (Path) {UUID} id The id of the webhook to delete
@apiSuccess (201) {String} type The type of the webhook
@apiSuccess {Object} options The options for the webhook (See webhook add examples)
""",
"""@api {delete} /api/v3/user/webhook/:id Delete a webhook - BETA
@apiParam (Path) {UUID} id The id of the webhook to delete
@apiSuccess {String} type The type of the webhook
@apiSuccess (201) {Object} options The options for the webhook (See webhook add examples)
""",
]
# pylint: disable=missing-docstring
endpoint_attrs = ('method', 'uri', 'title')
expected_endpoints = [
    ('post', '/api/v3/user/webhook', 'Create a new webhook - BETA'),
    ('put', '/api/v3/user/webhook/:id', 'Edit a webhook - BETA'),
    ('delete', '/api/v3/user/webhook/:id', 'Delete a webhook - BETA')
]

class TestParse(unittest.TestCase):
    def setUp(self):
        self.file = tempfile.NamedTemporaryFile(delete=False)

    def tearDown(self):
        os.remove(self.file.name)

    def test_read(self):
        self.file.write(test_data.encode('utf-8'))
        self.file.close()
        ret = parse_apidoc(self.file.name)
        self.assertEqual(len(ret), 3)

    def test_wrong_apidoc0(self):
        self.file.write(wrong_apidoc_data[0].encode('utf-8'))
        self.file.close()
        with self.assertRaises(ValueError):
            ret = parse_apidoc(self.file.name)

    def test_wrong_apidoc1(self):
        self.file.write(wrong_apidoc_data[1].encode('utf-8'))
        self.file.close()
        with self.assertRaises(ValueError):
            ret = parse_apidoc(self.file.name)


class TestParsedEndpoints(unittest.TestCase):
    def setUp(self):
        self.file = tempfile.NamedTemporaryFile(delete=False)
        self.file.write(test_data.encode('utf-8'))
        self.file.close()
        self.ret = parse_apidoc(self.file.name)
        os.remove(self.file.name)

    def test_read(self):
        [self.assertIsInstance(x, ApiEndpoint) for x in self.ret]  # pylint: disable=W0106
        for expected_values, obj in zip(expected_endpoints, self.ret):
            for attr, expected in zip(endpoint_attrs, expected_values):
                self.assertEqual(getattr(obj, attr), expected)

    def test_retcodes(self):
        for retcode, obj in zip([201,200,200], self.ret):
            self.assertEqual(obj.retcode, retcode)
