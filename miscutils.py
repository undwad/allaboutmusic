### MISCUTILS ###

import sys, os, json, glob, re, gc, traceback, importlib, inspect
from pathlib         import Path
from os.path         import isdir, isfile
from traceback       import extract_tb
from threading       import get_ident
from collections.abc import Iterable 
from functools       import partial
from pprint          import pprint
from time            import *

true      = True
false     = False
null      = None
undefined = None

# DEBUG #

loglevel = 1

def silent(*args): pass
def print0(*args): (print if loglevel >= 0 else silent)(f'<0> <{get_ident()}>', *args)
def print1(*args): (print if loglevel >= 1 else silent)(f'<1> <{get_ident()}>', *args)
def print2(*args): (print if loglevel >= 2 else silent)(f'<2> <{get_ident()}>', *args)
def print3(*args): (print if loglevel >= 3 else silent)(f'<3> <{get_ident()}>', *args)    

def most_recent_traceback(e=None):
    tb = e.__traceback__ if e else last(sys.exc_info())
    return extract_tb(tb,limit=-1)[0]

def most_recent_problem(e=None):
    tb = most_recent_traceback(e)
    return f'<{tb.name}> {tb.line}'

### FUNCTIONAL ###    

def  isnull(x): return not x
def notnull(x): return not not x
def  isnone(x): return x is None
def notnone(x): return x is not None

def   istext(x): return type(x) == str
def isnumber(x): return type(x) == int or type(x) == float

def flip(xy):
    x,y = xy
    return y,x

### PARSE ###

def extract_number(text, defval=0.):
    found = re.findall(r'(?=.*?\d)\d*[.,]?\d*', text) 
    found = found and found[-1]
    if found:
        found = found.replace(',','.')
        return float(found)
    return defval

# CONVERT #

def obj2dict(obj, keys=None, cond=lambda k: True):
    keys = keys or dir(obj)
    return dict([k,getattr(obj,k)] for k in keys if cond(k))

class dict2obj(object):
    def __init__(self, d):
        self._dict = d
        for k,v in d.items():
            if isinstance(v, (list, tuple)):
                setattr(self, k, [dict2obj(x) if isinstance(x, dict) else x for x in v])
            else:
                setattr(self, k, dict2obj(v) if isinstance(v, dict) else v)
    def __str__(self):
        return str(self._dict)   

# OOP #

def rename(newname):
    def decorator(f):
        f.__name__ = newname
        return f
    return decorator

class classproperty(object):
    def __init__(self, f):
        self.f = f
    def __get__(self, obj, owner):
        return self.f(owner)
    
def addmethod(cls):
    def decorator(func):
        setattr(cls, func.__name__, func)
        return func
    return decorator    

# CONTAINER #

def first(xx): 
    return next(iter(xx))

def second(xx): 
    i = iter(xx)
    next(i)
    return next(i)

def last(xx): 
    return first(reversed(xx))

def iterable(obj):
    return isinstance(obj, Iterable) and type(obj) != str

class ListContainer:
    def __init__(self, items):
        self.items = items
    def __getitem__(self, key):
        if callable(key): 
            return container([x for x in self.items if key(x)])
        if iterable(key): 
            return container([self.items[i] for i in key])        
        return self.items[key]
    def __contains__(self, item):
        if callable(item): 
            return next((True for x in self.items if item(x)), False)
        return item in self.items
    def __iter__(self):
        return iter(self.items)
    def __next__(self):
        return next(self.items)
    def __str__(self):
        return str(self.items)   
    
class DictContainer:
    def __init__(self, items):
        self.items = items
    def __getitem__(self, key):
        if callable(key): 
            return container(dict((k,v) for k,v in self.items.items() if key(k,v)))
        if iterable(key): 
            return container(dict((k,self.items[k]) for k in key))        
        return self.items[key]
    def __contains__(self, key):
        if callable(key): 
            return next((True for k,v in self.items.items() if key(k,v)), False)
        return key in self.items
    def __iter__(self):
        return iter(self.items.items())
    def __next__(self):
        return next(self.items.items())
    def __str__(self):
        return str(self.items)       

def container(items):
    if type(items) == dict: return DictContainer(items)
    if iterable(items):     return ListContainer(items)
    return DictContainer(obj2dict(items))
    
# THROTTLE #

class Throttle:
    def __init__(self,fn,interval,timefn=time):
        self.fn     = fn
        self.t      = timefn()
        self.dt     = interval      
        self.timefn = timefn
    def __call__(self,*args,**kwargs):
        t = self.timefn()
        if t - self.t > self.dt:
            self.t = t
            self.fn(*args,**kwargs)
    
def throttle(interval,timefn=time):
    def decorator(fn):
        return Throttle(fn,interval,timefn=timefn)
    return decorator

# COMPOSITION #

def compose(*ff):
    def composition(*args,**kwargs):
        for f in reversed(ff):
            x              = f(*args,**kwargs)
            is_args        = type(x) == tuple
            is_args_kwargs = is_args and len(x) == 2 and type(x[0]) == tuple and type(x[1]) == dict
            if is_args_kwargs:  args,kwargs = x
            elif is_args:       args,kwargs = x,{}
            else:               args,kwargs = (x,),{}
        return x
    return composition

class Composable:
    def __init__(self,x):
        if isinstance(x,Composable): self.f = x.f
        elif callable(x):            self.f = x
        else: raise Exception(f'invalid argument `{x}`')
    def __call__(self,*args,**kwargs):
        return self.f(*args,**kwargs)
    def __lshift__(self,other):              
        return Composable(compose(self,other))
    def __rshift__(self,other):              
        return Composable(compose(other,self))
    def __and__(self,other):
        def f(*args,**kwargs):
            return self(*args,**kwargs) and other(*args,**kwargs)
        return Composable(f)
    def __or__(self,other):
        def f(*args,**kwargs):
            return self(*args,**kwargs) or other(*args,**kwargs)
        return Composable(f)
    def __invert__(self):
        def f(*args,**kwargs):
            return not self(*args,**kwargs)
        return Composable(f)
    def __pow__(self, other):
        return Composable(partial(self.f,other))
    
def composable(f):
    return Composable(f)

# NETWORK #

def ip4addrs():
    from netifaces import interfaces, ifaddresses, AF_INET
    ip_list = []
    for interface in interfaces():
        ifaddrs = ifaddresses(interface)
        for link in ifaddrs.get(AF_INET,[]):
            ip_list.append(link['addr'])
    return ip_list

# MISC #

def time2str(t):
    return strftime("%b %d %Y %H:%M:%S", localtime(t))

def mtime(path):
    return os.path.getmtime(path)

def mtime2str(path):
    return time2str(mtime(path))

def ipynb2py(source, target, *keys, prefix='###', suffix='###'): 
    print0(source, mtime2str(source))
    from json import load
    with open(source) as notebook:
        data = load(notebook)
        with open(target,'w') as module:
            for cell in data['cells']:
                lines = cell['source']
                if type(lines) == str:
                    lines = lines.split('\n')
                line0  = (lines or [''])[0].strip()
                haskey = lambda key: line0 == f'{prefix} {key} {suffix}'
                if cell['cell_type'] == 'code' and any(map(haskey,keys)):
                    code = ''.join(lines)
                    module.write(code)
                    module.write('\n')
    print0(target, mtime2str(target))
    path = os.path.dirname(target)
    if path not in sys.path: 
        sys.path.append(path)
                    
def getmethods(inst):
    return inspect.getmembers(inst, predicate=inspect.ismethod)
    
def getclasses(inst):
    return inspect.getmembers(inst, predicate=inspect.isclass)
    
def reloadmodule(module):
    if type(module) == str:
        module = sys.modules[module]
    importlib.reload(module)
    
def savetext(path, text, encoding='utf-8'):    
    with open(path,'w',encoding=encoding) as file:
        file.write(text)
    print0(path, mtime2str(path))
        
def loadtext(path,encoding='utf-8'):    
    print0(path, mtime2str(path))
    with open(path,'r',encoding=encoding) as file:
        return file.read()
    
def joinsources(target, sources, separator='\n'):    
    with open(target,'w') as fout:       
        for source in sources:
            print1(source, mtime2str(source))
            with open(source,'r') as fin:         
                if callable(separator): sep = separator(source=source)  
                else:                   sep = separator
                fout.write(sep)    
                fout.write(fin.read())
    print0(target, mtime2str(target))

def validfilename(s):
    return ''.join([x if x.isalnum() else '_' for x in s])                 
    
def notifyme(msg, **kwargs):
    from requests import post
    url = 'https://api.pushover.net/1/messages.json?token=ajhpgiiie25dhehjek63q5w2p36r1r&user=umobvvsyqwdhxtgfmued18q6qxfee8';
    return post(url, data = { 'message': msg, **kwargs })
    
def showmetrics(prevmetrics, metrics):
    text = ''
    for key,value in metrics.items(): 
        pvalue = prevmetrics.get(key)
        if   not isnumber(pvalue) : ch = ''                
        elif not isnumber(value)  : ch = ''
        elif value  > pvalue      : ch = '↑'
        elif pvalue > value       : ch = '↓'
        else                      : ch = ''
        text += f"{key}: {value}{ch}\n"
    return text  

def splitfilepath(path):
    found = re.findall(r'(.+)-(\d+).(.+)',path)
    return found and found[0]

def getfilenum(path):
    path,num,sfx = splitfilepath(path)
    return int(num)

def nextfile(path):
    path,num,sfx = splitfilepath(path)
    pad,num      = len(num),int(num)
    return f'{path}-{(num+1):0>8d}.{sfx}'
    
def sortedfiles(path):
    paths = list(glob.glob(path)) 
    paths.sort(key=getfilenum)
    return paths   

def pos2line(text,pos):
    lines = text.split('\n')
    for (i,line) in enumerate(lines):        
        if pos < len(line): 
            return i+1
        pos -= len(line)
        
def ctxsearch(path, regexpr, filter='*.*'):
    global loglevel
    ll,loglevel = loglevel,-1
    result = []
    for x in Path(path).rglob(filter):
        if isdir(x): continue
        text  = loadtext(x)
        found = re.search(regexpr,text)
        if found:
            pos  = found.span()[0]
            line = pos2line(text,pos)
            result.append((x,line))
    loglevel = ll
    return result
 
def print_list(list, name='list', leftlen=10, rightlen=10, suffix=''):
    print(name+':',len(list))
    print(*list[:leftlen],'...',*list[-rightlen:])
    if suffix is not None: print(suffix)
        
def pprint_list(list, name='list', leftlen=10, rightlen=10, suffix=''):
    print(name+':',len(list))
    pprint((*list[:leftlen],'...',*list[-rightlen:]))
    if suffix is not None: print(suffix)
    
def loadfolder(folder):
    items = []
    for file in Path(folder).rglob('*.json'):
        tmp    = eval(loadtext(file))
        items += tmp
    return items
    
print('miscutils') 

