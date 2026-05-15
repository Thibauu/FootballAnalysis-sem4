import json
from pandas import DataFrame
from matplotlib.figure import Figure
from matplotlib.axes._axes import Axes
from box import Box
import hashlib
from df_checker import DfChecker
from figure_checker import FigureChecker



class Answer:
    def __init__(self, solution: str|dict = {}, ignore_check:bool = False):
        self._box = Box({})
        self._hash_dict = {}
        if isinstance(solution, str):
            with open(solution) as f:
                self._s = json.load(f) 
        else: 
            self._s = solution
        self._ignore_check = ignore_check
        self._checks = []

    def __getitem__(self, key):
        return self._box[key]
    
    def __setitem__(self, key, value) -> tuple:
        self._hash_dict[key] = self._hash(value)
        self._box[key] =  value

    def __getattr__(self, key):
        return getattr(self._box, key)

    def __setattr__(self, key, value):
        if key in ["_box",'_hash_dict', '_s', '_ignore_check', '_checks']:
            super().__setattr__(key, value)
        else:
            self.__setitem__(key, value)

    def _hash(self, value) -> str:
        if isinstance(value, DataFrame):
            return DfChecker.hash(value)
        elif isinstance(value, Figure):
            return FigureChecker.hash(value)
        elif isinstance(value, Axes):
            fig = value.get_figure()
            return FigureChecker.hash(fig)
        elif isinstance(value, list):
            return FigureChecker.hash(value[0])
        elif isinstance(value, str):
            hash_object = hashlib.md5(value.encode())
            return hash_object.hexdigest()
        ## scipy.stats._stats_py.NormaltestResult
        raise NotImplementedError

    @property
    def hash_dict(self):
        return self._hash_dict
    
    def is_equal(self, key) -> bool:
        return self._hash_dict[key] == self._s[key] 
        
    def check(self, key) -> str:
        self._checks.append(key)

        if self._ignore_check:
            return 'Check is ignored.'
        elif self.is_equal(key):
            return '<h3 style="color: green">Your answer is correct!</h3>'
        return '<h3 style="color: #D22B2B">Your answer is NOT correct!</h3>'
    
    def get_checks(self) -> DataFrame:
        return DataFrame(
            {'Check Key': self._checks, 
             'Result': [self.is_equal(k) for k in self._checks]
             })
    
    def hash_to_json(self) -> str:
        temp = {k:self._hash_dict[k] for k in self._checks} #only export relevant hashs
        return json.dumps(temp)
    
    def hash_to_file(self, fpath: str) -> None:
        with open(fpath, mode='w', encoding='utf8') as f:
            f.write(self.hash_to_json())


def hash_me(value) -> str:
    if isinstance(value, DataFrame):
        return DfChecker.hash(value)
    elif isinstance(value, Figure):
        return FigureChecker.hash(value)
    elif isinstance(value, Axes):
        fig = value.get_figure()
        return FigureChecker.hash(fig)
    elif isinstance(value, (int, float)):
        normalized_value = round(float(value), 2)
        return str(normalized_value)
    else:
        return str(value)


if __name__ == "__main__":
    pass