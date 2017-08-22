from .api import Habitipy

class HabitipyAsync(Habitipy):
     async def __call__(self, session, **kwargs):
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
        reqyest_kwargs = dict(headers=headers, params=query)
        if method in ['put', 'post', 'delete']:
            request_kwargs['data']=json.dumps(kwargs)
        async with request(*request_args, **request_kwargs) as resp:
            if resp.status != self._node.retcode:
                resp.raise_for_status()
                msg = _("""
                Got return code {res.status_code}, but {node.retcode} was
                expected for {node.uri}. It may be a typo in Habitica apiDoc.
                Please file an issue to https://github.com/HabitRPG/habitica/issues""")
                msg = textwrap.dedent(msg)
                msg = msg.replace('\n', ' ').format(res=res, node=self._node)
                if self._strict:
                    raise WrongReturnCode(msg)
                else:
                    warnings.warn(msg)
            return (await resp.json())['data']
