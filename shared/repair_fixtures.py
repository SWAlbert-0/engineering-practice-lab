"""Three original, versioned teaching repositories. Not an external benchmark."""
import ast
import hashlib
import json

PROTOCOL='d11-1'
CASES={
 'boundary':{'title':'运费规则','category':'边界条件','path':'src/shipping.py','fn':'shipping',
  'issue':'订单金额大于等于 100 元免运费，否则运费为 10 元。请修复临界金额的处理，并保留其他金额的行为。',
  'before':'def shipping(total):\n    return 0 if total > 100 else 10\n',
  'correct':'def shipping(total):\n    return 0 if total >= 100 else 10\n',
  'wrong':'def shipping(total):\n    return 0\n',
  'tests':[(0,10),(99,10),(100,0),(101,0)],'acceptance':[(50,10),(99.99,10),(100.01,0)]},
 'empty':{'title':'统计工具','category':'空输入','path':'src/statistics.py','fn':'average',
  'issue':'平均值函数接收数值列表。空列表返回 0，非空列表仍按算术平均值返回结果。',
  'before':'def average(values):\n    return sum(values) / len(values)\n',
  'correct':'def average(values):\n    return sum(values) / len(values) if values else 0\n',
  'wrong':'def average(values):\n    return 0\n',
  'tests':[([],0),([2,4],3),([0],0),([-3,3],0)],'acceptance':[([4,8,12],8),([-2,-4],-3),([0.5,1.5],1)]},
 'dedupe':{'title':'集合处理','category':'顺序保持','path':'src/collections.py','fn':'unique',
  'issue':'去除列表中的重复元素，同时保留各元素首次出现的顺序。空列表应返回空列表。',
  'before':'def unique(values):\n    return sorted(set(values))\n',
  'correct':'def unique(values):\n    return list(dict.fromkeys(values))\n',
  'wrong':'def unique(values):\n    return values\n',
  'tests':[([3,1,3,2],[3,1,2]),([],[]),([1,1],[1]),([2,1],[2,1])],'acceptance':[([5,2,5,1],[5,2,1]),([9,9,8],[9,8]),([0,-1,0],[0,-1])]}}

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(value):return hashlib.sha256((value if isinstance(value,str) else canonical(value)).encode('utf-8')).hexdigest()
def snapshot(key):
    case=CASES[key]
    tests={'regression':case['tests'],'acceptance':case['acceptance']}
    body={'protocol':PROTOCOL,'repository':key,'path':case['path'],'source':case['before'],'fn':case['fn'],'issue':case['issue'],'tests':tests,'offline_candidates':{'correct':digest(case['correct']),'wrong':digest(case['wrong'])}}
    return {'repository':key,'title':case['title'],'category':case['category'],'path':case['path'],'issue':case['issue'],
            'source':case['before'],'source_sha256':digest(case['before']),'tests_sha256':digest(tests),'snapshot_sha256':digest(body),
            'regression_count':len(case['tests']),'acceptance_count':len(case['acceptance']),'protocol':PROTOCOL,
            'tests':[{'id':('REG' if group=='regression' else 'ACC')+f'-{i:02}','group':group,'input':value,'expected':expected}
                     for group,pairs in (('regression',case['tests']),('acceptance',case['acceptance'])) for i,(value,expected) in enumerate(pairs,1)]}

SAFE_BUILTINS=('sum','len','list','dict','set','range','sorted','abs','min','max','enumerate','zip','reversed','all','any','round','int','float','str','bool','tuple')
_ALLOWED=('Module','FunctionDef','arguments','arg','Return','If','IfExp','For','While','Break','Continue','Pass','Assign','AugAssign','Expr',
          'Name','Load','Store','Constant','Call','Attribute','keyword','List','Tuple','Set','Dict','Subscript','Slice',
          'BinOp','UnaryOp','BoolOp','Compare','Add','Sub','Mult','Div','FloorDiv','Mod','Pow','USub','UAdd','Not','And','Or',
          'Eq','NotEq','Lt','LtE','Gt','GtE','Is','IsNot','In','NotIn','ListComp','SetComp','DictComp','GeneratorExp','comprehension')
def validate_source(source,key):
    if not isinstance(source,str) or not 1<=len(source.encode('utf-8'))<=12000:raise ValueError('候选文件应为 1–12000 UTF-8 字节。')
    try:tree=ast.parse(source)
    except (SyntaxError,ValueError,RecursionError):raise ValueError('候选 Python 语法无效。') from None
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef):raise ValueError('仅允许修改指定函数，不允许模块级动作或额外定义。')
    fn=tree.body[0]
    if fn.name!=CASES[key]['fn'] or len(fn.args.args)!=1 or fn.args.posonlyargs or fn.args.kwonlyargs or fn.args.vararg or fn.args.kwarg or fn.args.defaults or fn.decorator_list or fn.returns or fn.args.args[0].annotation:
        raise ValueError('必须保留原函数名和单参数签名，不允许装饰器或默认表达式。')
    for node in ast.walk(tree):
        if type(node).__name__ not in _ALLOWED:raise ValueError('候选使用了当前受控函数范围之外的语法：'+type(node).__name__)
        name=getattr(node,'id',None) or (node.arg if isinstance(node,ast.arg) else None)
        if name and name.startswith('_'):raise ValueError('不允许内部名称访问。')
        if isinstance(node,ast.Attribute) and not (node.attr=='fromkeys' and isinstance(node.value,ast.Name) and node.value.id=='dict'):
            raise ValueError('不允许对象属性访问；仅开放 dict.fromkeys。')
        if isinstance(node,ast.Call) and not (isinstance(node.func,ast.Name) and node.func.id in SAFE_BUILTINS+(fn.name,) or isinstance(node.func,ast.Attribute)):
            raise ValueError('调用超出允许的函数集合。')
    return source if source.endswith('\n') else source+'\n'

def validate_proposal(value,key):
    if not isinstance(value,dict) or set(value)!={'files','summary'}:raise ValueError('补丁需包含且仅包含 files 和 summary。')
    files=value['files'];summary=value['summary']
    if not isinstance(summary,str) or not 1<=len(summary.strip())<=1200:raise ValueError('补丁说明应为 1–1200 字。')
    if not isinstance(files,list) or len(files)!=1 or not isinstance(files[0],dict) or set(files[0])!={'path','content'}:raise ValueError('每轮只允许一个完整源文件。')
    if files[0]['path']!=CASES[key]['path']:raise ValueError('补丁路径不在白名单中；测试、配置和其他文件不可修改。')
    return {'path':files[0]['path'],'content':validate_source(files[0]['content'],key),'summary':summary.strip()}
