#!/usr/bin/env python3  
# Marllus Lustosa - 07-11-2025
# python3 CV_metric_final.py vm1_report.sar vm2_report.sar

import subprocess  
import sys  
import pandas as pd  
import numpy as np  
  
def load_sar(filename, flag, column):  
   cmd = f"sadf -d {filename} -- {flag}"  
   out = subprocess.check_output(cmd, shell=True).decode("utf-8")  
  
   df = pd.read_csv(pd.io.common.StringIO(out), sep=';')  
  
   # Remove '#' do início da primeira coluna e tira espaços extras  
   df.columns = df.columns.str.replace('#', '', regex=False).str.strip()  
  
   # Troca vírgula decimal por ponto  
   if column in df.columns:  
       df[column] = df[column].astype(str).str.replace(',', '.', regex=False)  
       df[column] = pd.to_numeric(df[column], errors='coerce')  
       return df[column].dropna()  
   else:  
       print(f"[debug] Colunas disponíveis: {list(df.columns)}")  
       return None  
  
def stats(series):  
   mean = series.mean()  
   median = series.median()  
   std = series.std()  
   cv = std / mean if mean != 0 else np.nan  
   return mean, median, std, cv  
  
def show(metric_name, series):  
   if series is None:  
       print(f"{metric_name:<12}:  (coluna não encontrada)")  
       return  
      
   mean, median, std, cv = stats(series)  
   print(f"{metric_name:<12}: Média={mean:.2f} | Mediana={median:.2f} | Desvio={std:.2f} | CV={cv:.3f}")  
  
   if cv <= 0.30:  
       print("   → Baixa variação → **Use Média**")  
   elif cv > 1.0:  
       print("   → Alta variação → **Use Mediana**")  
   else:  
       print("   → Variação moderada → Ambas são aceitáveis")  
  
def process(vm, name):  
   print(f"\n=== {name} ===")  
  
   show("CPU_User",       load_sar(vm, "-u", "%user"))  
   show("CPU_System",     load_sar(vm, "-u", "%system"))  
   show("Mem_Used",       load_sar(vm, "-r", "%memused"))  
   show("Swap_Used",      load_sar(vm, "-S", "%swpused"))  
   show("IO_TPS",         load_sar(vm, "-b", "tps"))  
  
def main():  
   if len(sys.argv) != 3:  
       print("Uso: python3 CV_metric_final.py vm1_report.sar vm2_report.sar")  
       sys.exit(1)  
  
   process(sys.argv[1], "VM1")  
   process(sys.argv[2], "VM2")  
  
   print("""  
Interpretação do CV:  
 CV <= 0.30  → Média representa bem (baixa variação)  
 CV >  1.00  → Mediana é mais confiável (muita oscilação / picos)  
""")  
  
if __name__ == "__main__":  
   main()
