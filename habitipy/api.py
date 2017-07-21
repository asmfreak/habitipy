#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Phil Adams http://philadams.net

Python wrapper around the Habitica (http://habitica.com) API
http://github.com/philadams/habitica
"""


import json
from typing import Tuple, Dict, Union

import requests

API_URI_BASE = 'api/v3'
API_CONTENT_TYPE = 'application/json'


class Habitica(object):
    """
    A minimalist Habitica API class.
    """

    def __init__(self, auth:Dict=None, resource:str=None, aspect:str=None) -> None:
        self.auth = auth
        self.resource = resource
        self.aspect = aspect
        self.headers = auth if auth else {}  # type: Dict
        self.headers.update({'content-type': API_CONTENT_TYPE})

    def __getattr__(self, m: str) -> 'Habitica':
        try:
            return object.__getattr__(self, m)  # type: ignore
        except AttributeError:
            if not self.resource:
                return Habitica(auth=self.auth, resource=m)
            else:
                return Habitica(auth=self.auth, resource=self.resource,
                                aspect=m)

    def _build_uri(self, **kwargs) -> Tuple[str, Dict]:
        # build up URL... Habitica's api is the *teeniest* bit annoying
        # so either i need to find a cleaner way here, or i should
        # get involved in the API itself and... help it.
        aspect_id = kwargs.pop('_id', None)
        direction = kwargs.pop('_direction', None)
        uri = '%s/%s' % (self.auth['url'], API_URI_BASE)
        if self.aspect:
            if aspect_id is not None:
                uri_template = "{0}/{self.aspect}/{aspect_id}"
            elif self.aspect == 'tasks':
                uri_template = "{0}/{self.aspect}/{self.resource}"
            else:
                uri_template = "{0}/{self.resource}/{self.aspect}"
            if direction is not None:
                uri_template += "/score/{direction}"
        else:
            uri_template = '{0}/{self.resource}'
        # for strange urls
        _uri_template = kwargs.pop('_uri_template', None)
        if _uri_template:
            uri_template = _uri_template
        uri = uri_template.format(
              uri, self=self, aspect_id=aspect_id, direction=direction)
        return uri, kwargs

    def __call__(self, **kwargs) -> Dict:
        method = kwargs.pop('_method', 'get')

        uri, kwargs = self._build_uri( **kwargs)

        # actually make the request of the API
        if method in ['put', 'post', 'delete']:
            res = getattr(requests, method)(uri, headers=self.headers,
                                            data=json.dumps(kwargs))
        else:
            res = getattr(requests, method)(uri, headers=self.headers,
                                            params=kwargs)

        # print(res.url)  # debug...
        if res.status_code not in [requests.codes.ok, requests.codes.created]:
            res.raise_for_status()
        return res.json()["data"]

def n():
    pass

from collections import defaultdict, namedtuple
import re
import warnings
import pkg_resources

class ParamAlreadyExist(ValueError):
    pass

class ApiNode(object):
    def __init__(self, param_name = None, param=None, paths=None):
        self.param = param
        self.param_name = None
        self.paths = paths or {}

    def into(self, val: str):
        if val in self.paths:
            return self.paths[val]
        if self.param:
            return self.param
        raise IndexError("Value {} is missing from api".format(val))

    def can_into(self, val: str):
        return val in self.paths or (self.param and self.param_name == val)

    def place(self, part: str, val: Union['ApiNode', 'ApiEndpoint']):
        if part.startswith(':'):
            if self.param and self.param != part:
                err = 'Cannot place param "{}" as "{self.param_name}" exist on node already!'
                raise ParamAlreadyExist(err.format(part, self=self))
            self.param = val
            self.param_name = part
            return val
        self.paths[part] = val
        return val

    def keys(self):
        if self.param:
            yield self.param_name
        yield from self.paths.keys()

    def __repr__(self):
        text = '<ApiNode {self.param_name}: {self.param} paths: {self.paths}>'
        return text.format(self=self)


class Api(object):
    def __init__(self, auth, apis=None, current=None, from_github=False, branch=None):
        self._auth = auth
        if isinstance(apis, (type(None), list)):
            if not apis:
                fn = pkg_resources.resource_filename('habitipy', 'apidoc.txt')
                fn = branch if from_github else fn
                apis = parse_apidoc(fn, from_github)
            apis = self._make_apis_dict(apis)
        if isinstance(apis, ApiNode):
            self._apis = apis
        else:
            raise ValueError('Possible apis {} have wrong type({})'.format(apis, type(apis)))
        current = current or ['api', 'v3']
        if not isinstance(current, list):
            raise ValueError('Wrong current api position {}'.format(current))
        _node = self._apis
        for part in current:
            _node = _node.into(part)
        self._node = _node
        self._current = current
        self._is_request = isinstance(self._node, ApiEndpoint)
        if self._is_request:
            self.__doc__ = self._node.render_docstring()

    @staticmethod
    def _make_apis_dict(apis):
        node = ApiNode()
        for api in apis:
            cur_node = node
            prev_part = ''
            for part in api.parted_uri:
                if cur_node.can_into(part):
                    _node = cur_node.into(part)
                else:
                    try:
                        _node = cur_node.place(part, ApiNode())
                    except ValueError:
                        warnings.warn('Ignoring conflicting param. Don\'t use {}'.format(api.uri))
                        _node = cur_node.param
                cur_node = _node
                prev_part += '/' + part
            cur_node.place(api.method, api)
        return node

    def _make_headers(self):
        headers = self._auth if self._auth else {}
        headers.update({'content-type': API_CONTENT_TYPE})
        return headers

    def __dir__(self):
        return super().__dir__() + list(self._node.keys())

    def __getattr__(self, val):
        if val in dir(super()):
            return super().__getattr__(val)
        try:
            _node = self._node.into(val)
            return Api(self._auth, apis=self._apis, current=self._current + [val])
        except ValueError:
            pass
        raise AttributeError('{} not found in this API!'.format(val))

    def __getitem__(self, val):
        try:
            _node = self._node.into(val)
            return Api(self._auth, apis=self._apis, current=self._current + [val])
        except ValueError:
            pass
        raise IndexError('{} not found in this API!'.format(val))

    def __call__(self, **kwargs):
        uri = '/' + '/'.join(self._current[-1])
        if not self._is_request:
            raise ValueError('{} is not an endpoint!'.format(uri))

API_URI_BASE = '/api/v3'
def download_api(branch=None):
    'download API documentation from _branch_ of Habitica\'s repo on Github'
    from plumbum import local
    habitica_github_api = 'https://api.github.com/repos/HabitRPG/habitica'
    if not branch:
        branch = requests.get(habitica_github_api + '/releases/latest').json()['tag_name']
    curl = local['curl']['-sL', habitica_github_api + '/tarball/{}'.format(branch)]
    tar = local['tar'][
        'axzf', '-', '--wildcards', '*/website/server/controllers/api-v3/*', '--to-stdout']
    grep = local['grep']['@api']
    sed = local['sed']['-e', 's/^[ */]*//g', '-e', 's/  / /g', '-']
    return (curl | tar | grep | sed)()


def parse_apidoc(file_or_branch, from_github=False):
    'read file and parse apiDoc lines'
    apis = []
    regex = r'(?P<group>\([^)]*\)){0,1} *(?P<type_>{[^}]*}){0,1} *'
    regex += r'(?P<field>[^ ]*) *(?P<description>.*)$'
    param_regex = re.compile(r'^@apiParam {1,}'+regex)
    success_regex = re.compile(r'^@apiSuccess {1,}'+regex)
    if from_github:
        text = download_api(file_or_branch)
    else:
        with open(file_or_branch) as f:
            text = f.read()
    for line in text.split('\n'):
        line = line.replace('\n', '')
        if line.startswith('@api '):
            split_line = line.split(' ')
            assert len(split_line) >= 3
            method = split_line[1]
            uri = split_line[2]
            assert method[0] == '{'
            assert method[-1] == '}'
            method = method[1:-1]
            assert uri.startswith(API_URI_BASE)
            title = ' '.join(split_line[3:])
            apis.append(ApiEndpoint(method, uri, title))
        elif line.startswith('@apiParam '):
            res = next(param_regex.finditer(line)).groupdict()
            print(res)
            apis[-1].param(**res)
        elif line.startswith('@apiSuccess '):
            res = next(success_regex.finditer(line)).groupdict()
            apis[-1].success(**res)
    return apis


class ApiEndpoint(object):
    def __init__(self, method, uri, title=''):
        self.method = method
        self.uri = uri
        self.parted_uri = uri[1:].split('/')
        self.title = title
        self.params = defaultdict(dict)
        self.retcode = None

    def param(self, group=None, type_='', field='', description=''):
        group = group or '(Parameter)'
        group = group.lower()[1:-1]
        p = Param(type_, field, description)
        self.params[group][p.field] = p

    def success(self, group=None, type_='', field='', description=''):
        group = group or '(200)'
        group = group.lower()[1:-1]
        self.retcode = self.retcode or group
        if group != self.retcode:
            raise ValueError('Two or more retcodes!')
        type_ = type_ or '{String}'
        p = Param(type_, field, description)
        self.params['responce'][p.field] = p


    def __repr__(self):
        return '<@api {{{self.method}}} {self.uri} {self.title}>'.format(self=self)

    def render_docstring(self):
        res = '{{{self.method}}} {self.uri} {self.title}\n'.format(self=self)
        if self.params:
            #res+='Request data\n'
            for group, params in self.params.items():
                res += group + ' group\n'
                for field, param in params.items():
                    res += param.render_docstring()
        return res

# TODO: fix type checking
_valid_types = {
    'string': lambda  x: isinstance(x, str),
    'sring': lambda  x: isinstance(x, str),
    'number': lambda x: isinstance(x, float)
}

class Param(object):
    'represents param of request or responce'
    def __init__(self, type_, field, description):
        self.is_optional = field[0] == '[' and field[-1] == ']'
        self.field = field[1:-1] if self.is_optional else field
        if '=' in self.field:
            self.field, self.default = self.field.split('=')
        else:
            self.default = ''
        self.field = self.field.split('.')
        if len(self.field) > 1:
            self.path, self.field = self.field[:-1], self.field[-1]
        else:
            self.field = self.field[0]
            self.path = []
        self.type = type_[1:-1] if len(type_) > 2 else type_
        if '=' in self.type:
            self.type, self.possible_values = self.type.split('=')
            self.possible_values = list(map(
                lambda s: s if s[0] != '"' else s[1:-1],
                self.possible_values.split(',')))
        else:
            self.possible_values = []
        self.type = self.type.lower()
        self.description = description

    def validate(self, val):
        pass

    def render_docstring(self):
        default = (' = ' +str(self.default)) if self.default else ''
        opt = 'optional' if self.is_optional else ''
        can_be = ' '.join(self.possible_values) if self.possible_values else ''
        can_be = 'can be one of [{}]'.format(can_be) if can_be else ''
        type_ = 'of type ' + self.type
        return ' '.join([opt, '"'+self.field+'"', default, type_, can_be, '\n']).replace('  ', ' ').lstrip()
