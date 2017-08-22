"""
    habitipy - tools and library for Habitica restful API
    RESTful api abstraction module with asyncio backend
"""
# pylint: disable=too-few-public-methods,invalid-name
import textwrap
import warnings
from typing import Union, Dict, List
import aiohttp  # pylint: disable=import-error

from .api import Habitipy, WrongReturnCode
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
    def __call__(   # type: ignore
            self,
            session: aiohttp.ClientSession,
            **kwargs) -> Union[Dict, List]:
        return self._request(*self._prepare_request(backend=session, **kwargs))

    async def _request(self, request, request_args, request_kwargs):
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
