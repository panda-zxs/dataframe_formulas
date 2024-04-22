# -*- coding: utf-8 -*-

from ..exceptions import TokenError


class Token(object):
    _re = None

    def __init__(self, s, context=None):
        self.source, self.attr = s, {}
        self.df = None
        self.custom_var_map = None
        m = self.match(s)
        self.end_match = m and m.end(0)
        if self.end_match:
            if m.groupdict().get("raise"):
                raise TokenError()
            self.attr.update(self.process(m, context))
        if not self.attr:
            raise TokenError()

    def ast(self, tokens, stack, builder):
        tokens.append(self)

    def update_input_tokens(self, *tokens):
        pass

    @property
    def node_id(self):
        return self.get_expr

    @property
    def name(self):
        return self.attr.get('name', '')

    def set_expr(self, *tokens):
        self.attr['expr'] = self.name

    def set_df(self, df):
        self.df = df

    def set_custom_var_map(self, custom_var_map):
        self.custom_var_map = custom_var_map

    def __getattr__(self, item):
        if item.startswith('has_'):
            return item[4:] in self.attr
        elif item.startswith('get_'):
            return self.attr[item[4:]]
        return super(Token, self).__getattr__(item)

    def __repr__(self):
        return '{} <{}>'.format(self.name, self.__class__.__name__)

    def __str__(self):
        return '{} <{}>'.format(self.name, self.__class__.__name__)

    def process(self, match, context=None):
        return {k: v for k, v in match.groupdict().items() if v is not None}

    def match(self, s):
        return self._re.match(s)
