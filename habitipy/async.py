import json
import textwrap
import warnings
import aiohttp
from typing import Union, Dict, List
from .api import Habitipy, ApiEndpoint, WrongReturnCode
from .util import get_translation_functions

_, ngettext = get_translation_functions('habitipy', names=('gettext', 'ngettext'))

class HabitipyAsync(Habitipy):
    """
    Habitipy API using aiohttp as backend for request

    ```python
    async def HabitipyAsync.__call__(
        self,
        session: aiohttp.ClientSession,
        **kwargs
    ) -> Union[Dict, List]
    ```
    # Arguments

    session (aiohttp.ClientSession): aiohttp session used to make request.

    # Example
    ```python
    import asyncio
    from aiohttp import ClientSession
    from habitipy import Habitipy, load_conf,DEFAULT_CONF
    from habitipy.async import HabitipyAsync


    loop = asyncio.new_event_loop()
    api = HabitipyAsync(load_conf(DEFAULT_CONF))

    async def main(api):
        async with ClientSession() as session:
            u = await api.user.get(session)
            return u
    loop.run_until_complete(main(api))
    ```
    """

    async def __call__(
        self,
        session: aiohttp.ClientSession,
        **kwargs
    ) -> Union[Dict, List]:
        uri = '/'.join([self._conf['url']] + self._current[:-1])
        if not isinstance(self._node, ApiEndpoint):
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
        request = getattr(session, method)
        request_args = (uri,)
        request_kwargs = dict(headers=headers, params=query)
        if method in ['put', 'post', 'delete']:
            request_kwargs['data'] = json.dumps(kwargs)
        async with request(*request_args, **request_kwargs) as resp:
            if resp.status != self._node.retcode:
                resp.raise_for_status()
                msg = _("""
                Got return code {res.status}, but {node.retcode} was
                expected for {node.uri}. It may be a typo in Habitica apiDoc.
                Please file an issue to https://github.com/HabitRPG/habitica/issues""")
                msg = textwrap.dedent(msg)
                msg = msg.replace('\n', ' ').format(res=resp, node=self._node)
                if self._strict:
                    raise WrongReturnCode(msg)
                else:
                    warnings.warn(msg)
            return (await resp.json())['data']
