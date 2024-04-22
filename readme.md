# dataframe add new column by str formula

```python
from dataframe_formulas import Parser
import vaex

if __name__ == "__main__":
    df = vaex.open("demo.csv")
    p = Parser(df=df, custom_var_map={})
    # formula_str = """=Org+'Org1'"""
    # formula_str = """=appAge+100"""
    formula_str = """=if(Org='Org1', 1, 0)"""
    column_info, new_df = p.add_column(formula=formula_str, prefix="prefilter")
    print(column_info)
    print(new_df)
```