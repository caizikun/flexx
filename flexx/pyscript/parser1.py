"""

The basics
----------

Most types just work, common Python names are converted to their JavaScript
equivalents.

.. pyscript_example::
    
    # Simple operations
    3 + 4 -1
    3 * 7 / 9
    5**2
    7 // 2
    
    # Basic types
    [True, False, None]
    
    # Lists and dicts
    foo = [1, 2, 3]
    bar = {'a': 1, b: 2}


Slicing and subscriping
-----------------------

.. pyscript_example::

    # Slicing lists
    foo = [1, 2, 3, 4, 5]
    foo[2:]
    foo[2:-2]
    
    # Slicing strings
    bar = 'abcdefghij'
    bar[2:]
    bar[2:-2]
    
    # Subscripting
    foo = {'bar': 3}
    foo['bar']
    foo.bar  # Works in JS, but not in Python


Assignments
-----------

Declaration of variables is handled automatically. Also support for
tuple packing and unpacking (a.k.a. destructuring assignment).

.. pyscript_example::
    
    # Declare foo
    foo = 3
    
    # But not here
    bar.foo = 3
    
    # Pack items in an array
    a = 1, 2, 3
    
    # And unpack them
    a1, a2, a3 = a
    
    # Deleting variables
    del bar.foo


Comparisons
-----------

.. pyscript_example::
    
    # Identity
    foo is bar
    
    # Equality (loose equality in JS)
    foo == bar

    # Test for null
    foo is None
    
    # Test for JS undefined
    foo is undefined


Function calls
--------------

.. pyscript_example::
    
    # Buisiness as usual
    foo(a, b)
    
    # Support for star args (but not **kwargs)
    foo(*a)

"""

import ast

from .parser0 import Parser0, JSError, unify  # noqa


class Parser1(Parser0):
    
    ## Literals
    
    def parse_Num(self, node):
        return repr(node.n)
    
    def parse_Str(self, node):
        return repr(node.s)
    
    def parse_Bytes(self, node):
        raise JSError('No Bytes in JS')
    
    def parse_NameConstant(self, node):
        # Py3k
        M = {True: 'true', False: 'false', None: 'null'}
        return M[node.value]
    
    def parse_List(self, node):
        code = ['[']
        for child in node.elts:
            code += self.parse(child)
            code.append(', ')
        if node.elts:
            code.pop(-1)  # skip last comma
        code.append(']')
        return code
    
    def parse_Tuple(self, node):
        return self.parse_List(node)  # tuple = ~ list in JS
    
    def parse_Dict(self, node):
        code = ['{']
        for key, val in zip(node.keys, node.values):
            code += self.parse(key)
            code.append(': ')
            code += self.parse(val)
            code.append(', ')
        if node.keys:
            code.pop(-1)  # skip last comma
        code.append('}')
        return code
        
    def parse_Set(self, node):
        raise JSError('No Set in JS')
    
    ## Variables
    
    def parse_Name(self, node):
        # node.ctx can be Load, Store, Del -> can be of use somewhere?
        id = node.id
        if id in self.vars:
            id = self.with_prefix(id)
        else:
            id = self.NAME_MAP.get(id, id)
        return id
    
    def parse_Starred(self, node):
        raise JSError('Starred args are not supported.')
    
    ## Expressions
    
    def parse_Expr(self, node):
        # Expression (not stored in a variable)
        code = [self.lf()]
        code += self.parse(node.value)
        code.append(';')
        return code
    
    def parse_UnaryOp(self, node):
        op = self.UNARY_OP[node.op.__class__.__name__]
        right = unify(self.parse(node.operand))
        return op, right
    
    def parse_BinOp(self, node):
        # from py2js
        # if isinstance(node.op, ast.Mod) and isinstance(node.left, ast.Str):
        #     left = self.parse(node.left)
        #     if isinstance(node.right, (ast.Tuple, ast.List)):
        #         right = self.visit(node.right)
        #         return "vsprintf(js(%s), js(%s))" % (left, right)
        #     else:
        #         right = self.visit(node.right)
        #         return "sprintf(js(%s), %s)" % (left, right)
        left = unify(self.parse(node.left))
        right = unify(self.parse(node.right))
        
        if isinstance(node.op, ast.Pow):
            return ["Math.pow(", left, ", ", right, ")"]
        elif isinstance(node.op, ast.FloorDiv):
            return ["Math.floor(", left, "/", right, ")"]
        else:
            op = ' %s ' % self.BINARY_OP[node.op.__class__.__name__]
            return [left, op, right]
    
    def parse_BoolOp(self, node):
        op = ' %s ' % self.BOOL_OP[node.op.__class__.__name__]
        values = [unify(self.parse(val)) for val in node.values]
        return op.join(values)
    
    def parse_Compare(self, node):
        
        if len(node.ops) != 1:
            raise JSError('Comparisons with multiple ops is not supported.')
        if len(node.comparators) != 1:
            raise JSError('Comparisons with multiple comps is not supported.')
        
        opnode = node.ops[0]
        comp = node.comparators[0]
        op = self.COMP_OP[opnode.__class__.__name__]
        
        if isinstance(op, ast.In):
            raise JSError('The "in" operator is currently not supported.')
        elif isinstance(op, ast.NotIn):
            raise JSError('The "in" operator is currently not supported.')
        
        left = unify(self.parse(node.left))
        right = unify(self.parse(comp))
        return "%s %s %s" % (left, op, right)
    
    def parse_Call(self, node):
        
        # Get full function name and method name if it exists
        if isinstance(node.func, ast.Attribute):
            method_name = node.func.attr
            base_name = unify(self.parse(node.func.value))
            full_name = base_name + '.' + method_name
        else:
            method_name = ''
            base_name = ''
            full_name = unify(self.parse(node.func))
        
        # Handle special functions and methods
        res = None
        if method_name in self._methods:
            res = self._methods[method_name](node, base_name)
        elif full_name in self._functions:
            res = self._functions[full_name](node)
        if res is not None:
            return res
        
        # Handle normally
        if base_name.endswith('._base_class'):  # super() was used
            return [full_name] + self._get_args(node, 'this', True)
        else:
            code = [full_name] + self._get_args(node, base_name)
            # Insert "new" if this looks like a class
            if ((full_name and full_name[0].upper() == full_name[0]) or
                (method_name and method_name[0].upper() == method_name[0])):
                code.insert(0, 'new ')
            return code
    
    def _get_args(self, node, base_name, use_call_or_apply=False):
        """ Get arguments for function call. Does checking for keywords and
        handles starargs. The first element in the returned list is either
        "(" or ".apply(".
        """
        # Check for keywords (not supported) after handling special functions
        if node.keywords:
            raise JSError('function calls do not support keyword arguments')
        if node.kwargs:
            raise JSError('function calls do not support **kwargs')
        
        base_name = base_name or 'null'
        
        # flatten args and add commas
        argswithcommas = []
        for arg in node.args:
            argswithcommas.extend(self.parse(arg))
            argswithcommas.append(', ')
        if argswithcommas:
            argswithcommas.pop(-1)
        
        if node.starargs:
            starname = ''.join(self.parse(node.starargs))
            code = ['.apply(', base_name, ', [']
            code += argswithcommas
            code += ['].concat(', starname, '))']
            return code
        elif use_call_or_apply:
            if argswithcommas:
                return [".call(", base_name, ', '] + argswithcommas + [")"]
            else:
                return [".call(", base_name, ")"]
        else:
            # Normal func
            return ["("] + argswithcommas + [")"]
    
    def parse_Attribute(self, node):
        return "%s.%s" % (unify(self.parse(node.value)), node.attr)
    
    ## Statements
    
    def parse_Assign(self, node):
        """ Variable assignment. """
        code = [self.lf()]
        
        # Parse targets
        tuple = []
        for target in node.targets:
            var = ''.join(self.parse(target))
            if isinstance(target, ast.Name):
                if '.' in var:
                    code.append(var)
                else:
                    self.vars.add(var)
                    code.append(self.with_prefix(var))
            elif isinstance(target, ast.Attribute):
                code.append(var)
            elif isinstance(target, ast.Subscript):
                code.append(var)
            elif isinstance(target, (ast.Tuple, ast.List)):
                dummy = self.dummy()
                code.append(dummy)
                tuple = [unify(self.parse(x)) for x in target.elts]
            else:
                raise JSError("Unsupported assignment type")
            code.append(' = ')
        
        # Parse right side
        code += self.parse(node.value)
        code.append(';')
        
        # Handle tuple unpacking
        if tuple:
            code.append(self.lf())
            for i, x in enumerate(tuple):
                self.vars.add(x)
                code.append('%s = %s[%i];' % (x, dummy, i))
        
        return code
    
    def parse_AugAssign(self, node):  # -> x += 1
        target = ''.join(self.parse(node.target))
        value = ''.join(self.parse(node.value))
        
        nl = self.lf()
        if isinstance(node.op, ast.Pow):
            return [nl, target, " = Math.pow(", target, ", ", value, ")"]
        elif isinstance(node.op, ast.FloorDiv):
            return [nl, target, " = Math.floor(", target, "/", value, ")"]
        else:
            op = ' %s= ' % self.BINARY_OP[node.op.__class__.__name__]
            return [nl, target, op, value]
    
    def parse_Delete(self, node):
        code = []
        for target in node.targets:
            code.append(self.lf('delete '))
            code += self.parse(target)
            code.append(';')
        return code
    
    def parse_Pass(self, node):
        return []

    ## Subscripting
    
    def parse_Subscript(self, node):
        
        value_list = self.parse(node.value)
        slice_list = self.parse(node.slice)
        
        code = []
        code += value_list
        
        if isinstance(node.slice, ast.Index):
            code.append('[')
            if slice_list[0].startswith('-'):
                code.append(unify(value_list) + '.length ')
            code += slice_list
            code.append(']')
        else:  # ast.Slice
            code.append('.slice(')
            code += slice_list
            code.append(')')
        return code
    
    def parse_Index(self, node):
        return self.parse(node.value)
    
    def parse_Slice(self, node):
        code = []
        if node.step:
            raise JSError('Slicing with step not supported.')
        if node.lower:
            code += self.parse(node.lower)
        else:
            code.append('0')
        if node.upper:
            code.append(',')
            code += self.parse(node.upper)
        return code
    
    def parse_ExtSlice(self, node):
        raise JSError('Multidimensional slicing not supported in JS')
    
    
    ## Comprehensions
    
    # ListComp
    # SetComp
    # GeneratorExp
    # DictComp
    # comprehension
    
    ## Imports - no imports

    def parse_Import(self, node):
        raise JSError('Imports not supported.')
    
    def parse_ImportFrom(self, node):
        
        if ('.' + node.module).endswith('pyscript'):
            # User is probably importing names from here to allow
            # writing the JS code and command to parse it in one module.
            # Ignore this import.
            return []
        raise JSError('Imports not supported.')
    
    def parse_alias(self, node):
        raise JSError('Imports not supported.')
    
    def parse_Module(self, node):
        # Module level. Every piece of code has a module as the root.
        # Just pass body.
        
        # Get docstring, but only if in module mode (i.e. top stack has a name)
        docstring = ''
        if self._stack[0][1]:
            docstring = self.get_docstring(node)
        
        code = []
        if docstring:
            for line in docstring.splitlines():
                code.append(self.lf('// ' + line))
            code.append('\n')
        for child in node.body:
            code += self.parse(child)
        return code
