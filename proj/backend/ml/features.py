"""Official attribute descriptions of the Polish Companies Bankruptcy dataset (UCI)."""
DESC = {
1:"Net profit / total assets",2:"Total liabilities / total assets",3:"Working capital / total assets",
4:"Current assets / short-term liabilities",5:"Cash-based liquidity over operating expenses (days)",
6:"Retained earnings / total assets",7:"EBIT / total assets",8:"Book value of equity / total liabilities",
9:"Sales / total assets",10:"Equity / total assets",11:"(Gross profit + extraordinary items + financial expenses) / total assets",
12:"Gross profit / short-term liabilities",13:"(Gross profit + depreciation) / sales",14:"(Gross profit + interest) / total assets",
15:"Total liabilities x 365 / (gross profit + depreciation)",16:"(Gross profit + depreciation) / total liabilities",
17:"Total assets / total liabilities",18:"Gross profit / total assets",19:"Gross profit / sales",20:"Inventory x 365 / sales",
21:"Sales growth (sales n / sales n-1)",22:"Operating profit / total assets",23:"Net profit / sales",
24:"Gross profit (3 years) / total assets",25:"(Equity - share capital) / total assets",26:"(Net profit + depreciation) / total liabilities",
27:"Operating profit / financial expenses",28:"Working capital / fixed assets",29:"Logarithm of total assets",
30:"(Total liabilities - cash) / sales",31:"(Gross profit + interest) / sales",32:"Current liabilities x 365 / cost of products sold",
33:"Operating expenses / short-term liabilities",34:"Operating expenses / total liabilities",35:"Profit on sales / total assets",
36:"Total sales / total assets",37:"(Current assets - inventories) / long-term liabilities",38:"Constant capital / total assets",
39:"Profit on sales / sales",40:"(Current assets - inventory - receivables) / short-term liabilities",
41:"Total liabilities / ((operating profit + depreciation) x 12/365)",42:"Operating profit / sales",
43:"Receivables + inventory turnover (days)",44:"Receivables x 365 / sales",45:"Net profit / inventory",
46:"(Current assets - inventory) / short-term liabilities (quick ratio)",47:"Inventory x 365 / cost of products sold",
48:"EBITDA / total assets",49:"EBITDA / sales",50:"Current assets / total liabilities",51:"Short-term liabilities / total assets",
52:"Short-term liabilities x 365 / cost of products sold",53:"Equity / fixed assets",54:"Constant capital / fixed assets",
55:"Working capital",56:"(Sales - cost of products sold) / sales",57:"(Current assets - inventory - short-term liabilities) / (sales - gross profit - depreciation)",
58:"Total costs / total sales",59:"Long-term liabilities / equity",60:"Sales / inventory",61:"Sales / receivables",
62:"Short-term liabilities x 365 / sales",63:"Sales / short-term liabilities",64:"Sales / fixed assets"}
# Dimension for Financial Health Overview (only indicators that exist in the dataset)
CATEGORY = {}
for k in (3,4,40,46,50,5,12,33): CATEGORY[k]="Liquidity"
for k in (2,8,17,51,59,37,34,16): CATEGORY[k]="Leverage"
for k in (1,7,18,22,23,35,39,42,48,49,56,13,19): CATEGORY[k]="Profitability"
for k in (9,36,20,44,47,60,61,62,63,64,32,52,43): CATEGORY[k]="Operational Efficiency"
for k in (6,10,25,38,53,54,28,29): CATEGORY[k]="Capital Structure"
def name(i): return f"Attr{i}"
