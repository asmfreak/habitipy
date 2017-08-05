"""
    habitipy - tools and library for Habitica restful API
    RESTful api abstraction module using requests
"""
# pylint: disable=invalid-name,too-few-public-methods,too-many-locals, bad-continuation

import json
import re
import uuid
from keyword import kwlist
import warnings
import textwrap
from collections import defaultdict
from typing import Dict, Union, List, Iterator, Any

import pkg_resources
import requests
from plumbum import local

from .util import get_translation_functions

API_URI_BASE = '/api/v3'
API_CONTENT_TYPE = 'application/json'
APIDOC_LOCAL_FILE = '~/.local/habitipy'
_, ngettext = get_translation_functions('habitipy', names=('gettext', 'ngettext'))


class ParamAlreadyExist(ValueError):
    'Custom error type'
    pass


class WrongReturnCode(ValueError):
    'Custom error type'
    pass


class WrongData(ValueError):
    'Custom error type'
    pass


class ApiNode(object):
    'Represents a middle point in API'
    def __init__(self, param_name=None, param=None, paths=None):
        self.param = param
        self.param_name = param_name
        self.paths = paths or {}  # type: Dict[str, Union[ApiNode,ApiEndpoint]]

    def into(self, val: str) -> Union['ApiNode', 'ApiEndpoint']:
        'Get another leaf node with name `val` if possible'
        if val in self.paths:
            return self.paths[val]
        if self.param:
            return self.param
        raise IndexError(_("Value {} is missing from api").format(val))  # NOQA: Q000

    def can_into(self, val: str) -> bool:
        'Determine if there is a leaf node with name `val`'
        return val in self.paths or (self.param and self.param_name == val)

    def place(self, part: str, val: Union['ApiNode', 'ApiEndpoint']):
        'place a leaf node '
        if part.startswith(':'):
            if self.param and self.param != part:
                err = """Cannot place param '{}' as '{self.param_name}' exist on node already!"""
                raise ParamAlreadyExist(err.format(part, self=self))
            self.param = val
            self.param_name = part
            return val
        self.paths[part] = val
        return val

    def keys(self) -> Iterator[str]:
        'return all possible paths one can take from this ApiNode'
        if self.param:
            yield self.param_name
        yield from self.paths.keys()

    def __repr__(self) -> str:
        text = '<ApiNode {self.param_name}: {self.param} paths: {self.paths}>'
        return text.format(self=self)

    def is_param(self, val):
        """checks if val is this node's param"""
        return val == self.param_name


def escape_keywords(arr):
    'append _ to all python keywords'
    for i in arr:
        yield i if i not in kwlist else i + '_'


class Habitipy(object):
    """Represents Habitica API

    """
    def __init__(self, conf, *,
                 apis=None, current=None,
                 from_github=False, branch=None,
                 strict=False):
        self._conf = conf
        self._strict = strict
        if isinstance(apis, (type(None), list)):
            if not apis:
                fn = pkg_resources.resource_filename('habitipy', 'apidoc.txt')
                fn = branch if from_github else fn
                apis = parse_apidoc(fn, from_github)
            with warnings.catch_warnings():
                warnings.simplefilter('error' if strict else 'ignore')
                apis = self._make_apis_dict(apis)
        if isinstance(apis, ApiNode):
            self._apis = apis
        else:
            raise TypeError('Possible apis {} have wrong type({})'.format(apis, type(apis)))
        current = current or ['api', 'v3']
        if not isinstance(current, list):
            raise TypeError('Wrong current api position {}'.format(current))
        _node = self._apis
        for part in current:
            _node = _node.into(part)
        self._node = _node
        self._current = current
        self._is_request = isinstance(self._node, ApiEndpoint)
        if self._is_request:
            self.__doc__ = self._node.render_docstring()

    @staticmethod
    def _make_apis_dict(apis) -> ApiNode:
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
                    except ParamAlreadyExist:
                        warnings.warn('Ignoring conflicting param. Don\'t use {}'.format(api.uri))
                        _node = cur_node.param
                cur_node = _node  # type: ignore
                prev_part += '/' + part
            cur_node.place(api.method, api)
        return node

    def _make_headers(self):
        headers = {
            'x-api-user': self._conf['login'],
            'x-api-key': self._conf['password']
        } if self._conf else {}
        headers.update({'content-type': API_CONTENT_TYPE})
        return headers

    def __dir__(self):
        return super().__dir__() + list(escape_keywords(self._node.keys()))

    def __getattr__(self, val: str) -> Union[Any, 'Habitipy']:
        if val in dir(super()):
            # pylint: disable=no-member
            return super().__getattr__(val)  # type:ignore
        try:
            val = val if not val.endswith('_') else val.rstrip('_')
            _node = self._node.into(val)
            return Habitipy(self._conf, apis=self._apis, current=self._current + [val])
        except IndexError:
            pass
        raise AttributeError('{} not found in this API!'.format(val))

    def __getitem__(self, val):
        try:
            _node = self._node.into(val)
            return Habitipy(self._conf, apis=self._apis, current=self._current + [val])
        except IndexError:
            pass
        raise IndexError('{} not found in this API!'.format(val))

    def __call__(self, **kwargs) -> Union[Dict, List]:
        uri = '/'.join([self._conf['url']] + self._current[:-1])
        if not self._is_request:
            raise ValueError('{} is not an endpoint!'.format(uri))
        method = self._node.method
        headers = self._make_headers()
        query = {}
        if 'query' in self._node.params:
            for name, param in self._node.params['query'].items():
                if name in kwargs:
                    query[name] = kwargs.pop(name)
                elif not param.is_optional:
                    raise TypeError('Mandatory param {} is missing'.format(name))
        if method in ['put', 'post', 'delete']:
            res = getattr(requests, method)(
                uri, headers=headers, params=query, data=json.dumps(kwargs))
        else:
            res = getattr(requests, method)(uri, headers=headers, params=query)
        if res.status_code != self._node.retcode:
            res.raise_for_status()
            msg = """Got return code {res.status_code}, but {node.retcode} was
            expected for {node.uri}. It may be a typo in Habitica apiDoc.
            Plase file an issue to https://github.com/HabitRPG/habitica/issues"""
            msg = textwrap.dedent(msg)
            msg = msg.replace('\n', ' ').format(res=res, node=self._node)
            if self._strict:
                raise WrongReturnCode(msg)
            else:
                warnings.warn(msg)
        return res.json()['data']


def download_api(branch=None) -> str:
    'download API documentation from _branch_ of Habitica\'s repo on Github'
    habitica_github_api = 'https://api.github.com/repos/HabitRPG/habitica'
    if not branch:
        branch = requests.get(habitica_github_api + '/releases/latest').json()['tag_name']
    curl = local['curl']['-sL', habitica_github_api + '/tarball/{}'.format(branch)]
    tar = local['tar'][
        'axzf', '-', '--wildcards', '*/website/server/controllers/api-v3/*', '--to-stdout']
    grep = local['grep']['@api']
    sed = local['sed']['-e', 's/^[ */]*//g', '-e', 's/  / /g', '-']
    return (curl | tar | grep | sed)()


def parse_apidoc(
    file_or_branch,
    from_github=False,
    save_github_version=True
) -> List['ApiEndpoint']:
    'read file and parse apiDoc lines'
    apis = []  # type: List[ApiEndpoint]
    regex = r'(?P<group>\([^)]*\)){0,1} *(?P<type_>{[^}]*}){0,1} *'
    regex += r'(?P<field>[^ ]*) *(?P<description>.*)$'
    param_regex = re.compile(r'^@apiParam {1,}' + regex)
    success_regex = re.compile(r'^@apiSuccess {1,}' + regex)
    if from_github:
        text = download_api(file_or_branch)
        if save_github_version:
            apidoc_local = local.path(APIDOC_LOCAL_FILE)
            if not apidoc_local.dirname.exists():
                apidoc_local.dirname.mkdir()
            with open(apidoc_local, 'w') as f:
                f.write(text)
    else:
        with open(file_or_branch) as f:
            text = f.read()
    for line in text.split('\n'):
        line = line.replace('\n', '')
        if line.startswith('@api '):
            if apis:
                if not apis[-1].retcode:
                    apis[-1].retcode = 200
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
            apis[-1].add_param(**res)
        elif line.startswith('@apiSuccess '):
            res = next(success_regex.finditer(line)).groupdict()
            apis[-1].add_success(**res)
    if apis:
        if not apis[-1].retcode:
            apis[-1].retcode = 200
    return apis


class ApiEndpoint(object):
    """
    Represents a single api endpoint.
    """
    def __init__(self, method, uri, title=''):
        self.method = method
        self.uri = uri
        self.parted_uri = uri[1:].split('/')
        self.title = title
        self.params = defaultdict(dict)
        self.retcode = None

    def add_param(self, group=None, type_='', field='', description=''):
        'parse and append a param'
        group = group or '(Parameter)'
        group = group.lower()[1:-1]
        p = Param(type_, field, description)
        self.params[group][p.field] = p

    def add_success(self, group=None, type_='', field='', description=''):
        'parse and append a success data param'
        group = group or '(200)'
        group = int(group.lower()[1:-1])
        self.retcode = self.retcode or group
        if group != self.retcode:
            raise ValueError('Two or more retcodes!')
        type_ = type_ or '{String}'
        p = Param(type_, field, description)
        self.params['responce'][p.field] = p

    def __repr__(self):
        return '<@api {{{self.method}}} {self.uri} {self.title}>'.format(self=self)

    def render_docstring(self):
        'make a nice docstring for ipython'
        res = '{{{self.method}}} {self.uri} {self.title}\n'.format(self=self)
        if self.params:
            for group, params in self.params.items():
                res += '\n' + group + ' params:\n'
                for param in params.values():
                    res += param.render_docstring()
        return res


# TODO: fix type checking
_valid_types = {
    'string': lambda x: isinstance(x, str),
    'sring': lambda x: isinstance(x, str),
    'number': lambda x: isinstance(x, float),
    'uuid': lambda u: isinstance(u, str) and u.replace('-', '') == uuid.UUID(u).hex
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

    def validate(self, obj):
        'check if obj has this api param'
        if self.path:
            for i in self.path:
                obj = obj[i]
        obj = obj[self.field]

        raise NotImplementedError('Validation is not implemented yet')

    def render_docstring(self):
        'make a nice docstring for ipython'
        default = (' = ' + str(self.default)) if self.default else ''
        opt = 'optional' if self.is_optional else ''
        can_be = ' '.join(self.possible_values) if self.possible_values else ''
        can_be = 'one of [{}]'.format(can_be) if can_be else ''
        type_ = 'of type "' + self.type + '"'
        res = ' '.join([opt, '"' + self.field + '"', default, type_, can_be, '\n'])
        return res.replace('  ', ' ').lstrip()
