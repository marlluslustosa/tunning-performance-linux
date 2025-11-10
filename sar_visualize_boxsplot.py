#!/usr/bin/env python3
"""
Marllus Lustosa - 07-11-25
sar_visualize_boxsplot.py (versão adaptada com bloxsplot)

Lê arquivos report.sar gerados pelo comando:
  sar -u -r -S -b -o report.sar 1 60

Executa automaticamente:
  sar -u -r -S -b -f <report.sar>

Parseia as seções (CPU, MEMORY, SWAP, IO) de forma robusta,
plota comparativo entre duas VMs e imprime estatísticas.

Modificações:
 - Coloca a média de cada VM na legenda (ex: VM1 (Média=93.10))
 - Adiciona entre parênteses no título de cada gráfico as médias e
   um texto indicando qual direção é "melhor" (Mais alto melhor / Mais baixo melhor)
 - Mantém o parser que você indicou como funcional
"""

import subprocess
import sys
import re
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import numpy as np

# -----------------------
# Utilitários de parsing
# -----------------------
def run_sar_on_file(sarfile_path):
    """Executa: sar -u -r -S -b -f <sarfile_path> e retorna saída (texto)."""
    cmd = ["sar", "-u", "-r", "-S", "-b", "-f", str(sarfile_path)]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, encoding='utf-8', errors='ignore')
        return out
    except subprocess.CalledProcessError as e:
        print(f"Erro ao executar sar para {sarfile_path}:")
        print(e.output)
        raise

def normalize_num(s):
    """Converte string com vírgula para float; retorna None em falha."""
    if s is None:
        return None
    s = str(s).strip().replace(',', '.')
    try:
        return float(s)
    except Exception:
        return None

# -----------------------
# Parser robusto por header
# -----------------------
class SARDataParser2:
    def __init__(self):
        self.data = {}

    def parse_sar_output(self, content, vm_name):
        lines = content.splitlines()
        current_section = None
        header_cols = []
        buffer = []

        # regex para detectar timestamp início de linha: ex "12:00:01" ou "12:00:01 AM"
        time_re = re.compile(r'^\d{1,2}:\d{2}:\d{2}')

        def flush_section():
            nonlocal current_section, header_cols, buffer
            if not current_section or not header_cols or not buffer:
                current_section = None
                header_cols = []
                buffer = []
                return

            # Construir DataFrame a partir do buffer usando header_cols
            rows = []
            for ln in buffer:
                ln = ln.strip()
                if not ln:
                    continue
                if ln.lower().startswith('average') or 'média' in ln.lower():
                    continue
                parts = re.split(r'\s+', ln)
                if len(parts) < 2:
                    continue

                row = {}
                if len(parts) >= len(header_cols):
                    for idx, col in enumerate(header_cols):
                        if idx < len(parts):
                            row[col] = parts[idx]
                        else:
                            row[col] = None
                else:
                    offset = len(header_cols) - len(parts)
                    for idx, col in enumerate(header_cols):
                        part_index = idx - offset
                        row[col] = parts[part_index] if 0 <= part_index < len(parts) else None
                rows.append(row)

            if rows:
                df = pd.DataFrame(rows)
                df.columns = [c.strip() for c in df.columns]

                for col in df.columns:
                    if col is None:
                        continue
                    if col.lower() in ('timestamp', 'hr', 'time', 'hora'):
                        continue
                    df[col] = df[col].apply(lambda x: normalize_num(x) if isinstance(x, str) or x is not None else None)
                # Armazenar dataset
                self.data[f'{vm_name}_{current_section}'] = df
            current_section = None
            header_cols = []
            buffer = []

        for line in lines:
            l = line.strip()
            if not l:
                continue

            low = l.lower()

            # Detecção de headers
            if '%user' in l and 'cpu' in l.lower():
                header_cols = re.split(r'\s+', l)
                if not re.match(r'^\d', header_cols[0]):
                    if header_cols[0].lower() not in ('time', 'timestamp'):
                        header_cols = ['timestamp'] + header_cols
                current_section = 'CPU'
                buffer = []
                continue

            if ('kbmemfree' in low or 'kbmemused' in low) and '%memused' in low:
                header_cols = re.split(r'\s+', l)
                if not re.match(r'^\d', header_cols[0]):
                    header_cols = ['timestamp'] + header_cols
                current_section = 'MEMORY'
                buffer = []
                continue

            if 'kbswpfree' in low or 'kbswpused' in low:
                header_cols = re.split(r'\s+', l)
                if not re.match(r'^\d', header_cols[0]):
                    header_cols = ['timestamp'] + header_cols
                current_section = 'SWAP'
                buffer = []
                continue

            if 'tps' in low and ('wtps' in low or 'bwrtn' in low or 'bread' in low or 'wrtn' in low):
                header_cols = re.split(r'\s+', l)
                if not re.match(r'^\d', header_cols[0]):
                    header_cols = ['timestamp'] + header_cols
                current_section = 'IO'
                buffer = []
                continue

            if current_section and time_re.match(l):
                buffer.append(l)
                continue

            if ('linux' in low and 'node' in low) or 'média' in low or low.startswith('average:') or low.startswith('average'):
                flush_section()
                continue

            if current_section:
                if re.search(r'\d', l):
                    buffer.append(l)

        flush_section()

    def get_column_by_candidates(self, vm_section_key, candidates):
        """
        Retorna a primeira coluna que corresponder a qualquer candidato (case-insensitive substring)
        """
        if vm_section_key not in self.data:
            return None
        df = self.data[vm_section_key]
        cols = df.columns
        for cand in candidates:
            for c in cols:
                if c and cand.lower() in c.lower():
                    return c
        return None

# -----------------------
# Preferências de "melhor"
# -----------------------
# Ajuste aqui se quiser outra interpretação do que é "melhor" para cada métrica.
# Valores possíveis: 'higher' -> "Mais alto melhor", 'lower' -> "Mais baixo melhor"
metric_preferences = {
    'CPU_user': 'higher',        # %user: mais alto melhor (throughput)
    'CPU_system': 'lower',       # %system: mais baixo melhor (menos overhead do kernel)
    'MEMORY_used': 'higher',      # %memused: mais baixo melhor (menos pressão de memória)
    'SWAP_used': 'lower',        # %swpused: mais baixo melhor (menos swapping)
    'IO_tps': 'higher',          # tps: mais alto melhor (throughput)
    'IO_bytes': 'higher',        # bytes escritos/s: mais alto melhor (throughput)
}

# -----------------------
# Plots e estatísticas
# -----------------------
def create_time_series_plots(parser, vm1_label='VM1', vm2_label='VM2'):
    fig, axes = plt.subplots(4, 2, figsize=(20, 16))
    fig.suptitle('Séries Temporais - Comparação de Performance', fontsize=16, fontweight='bold', y=0.98)
    colors = {vm1_label: 'blue', vm2_label: 'red'}

    # helper para montar legenda com média
    def mean_str(series):
        if series is None or len(series.dropna()) == 0:
            return "N/A"
        return f"{series.mean():.2f}"

    # --- CPU ---
    vm1_cpu_key = f'{vm1_label}_CPU'
    vm2_cpu_key = f'{vm2_label}_CPU'
    if vm1_cpu_key in parser.data and vm2_cpu_key in parser.data:
        vm1_cpu = parser.data[vm1_cpu_key]
        vm2_cpu = parser.data[vm2_cpu_key]

        user_col = parser.get_column_by_candidates(vm1_cpu_key, ['%user', 'user'])
        system_col = parser.get_column_by_candidates(vm1_cpu_key, ['%system', 'system'])
        iowait_col = parser.get_column_by_candidates(vm1_cpu_key, ['%iowait', 'iowait'])
        idle_col = parser.get_column_by_candidates(vm1_cpu_key, ['%idle', 'idle'])

        # CPU % User
        if user_col:
            s1 = vm1_cpu[user_col].dropna().astype(float)
            s2 = vm2_cpu[user_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('CPU_user', 'higher')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'CPU - % User (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[0,0].plot(vm1_cpu.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[0,0].plot(vm2_cpu.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[0,0].set_title(title, fontweight='bold')
            axes[0,0].set_ylabel('Percentual (%)')
            axes[0,0].legend()
            axes[0,0].grid(True, alpha=0.3)
            axes[0,0].set_ylim(0, 100)

        # CPU % System
        if system_col:
            s1 = vm1_cpu[system_col].dropna().astype(float)
            s2 = vm2_cpu[system_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('CPU_system', 'lower')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'CPU - % System (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[0,1].plot(vm1_cpu.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[0,1].plot(vm2_cpu.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[0,1].set_title(title, fontweight='bold')
            axes[0,1].set_ylabel('Percentual (%)')
            axes[0,1].legend()
            axes[0,1].grid(True, alpha=0.3)

    # --- MEMORY ---
    vm1_mem_key = f'{vm1_label}_MEMORY'
    vm2_mem_key = f'{vm2_label}_MEMORY'
    if vm1_mem_key in parser.data and vm2_mem_key in parser.data:
        vm1_mem = parser.data[vm1_mem_key]
        vm2_mem = parser.data[vm2_mem_key]

        memused_col = parser.get_column_by_candidates(vm1_mem_key, ['%memused', 'memused'])
        kbactive_col = parser.get_column_by_candidates(vm1_mem_key, ['kbactive', 'active'])

        if memused_col:
            s1 = vm1_mem[memused_col].dropna().astype(float)
            s2 = vm2_mem[memused_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('MEMORY_used', 'lower')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'Memória - % Utilizada (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[1,0].plot(vm1_mem.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[1,0].plot(vm2_mem.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[1,0].set_title(title, fontweight='bold')
            axes[1,0].set_ylabel('Percentual (%)')
            axes[1,0].legend()
            axes[1,0].grid(True, alpha=0.3)

        if kbactive_col:
            s1 = vm1_mem[kbactive_col].dropna().apply(lambda x: x/1024 if x is not None else None).astype(float)
            s2 = vm2_mem[kbactive_col].dropna().apply(lambda x: x/1024 if x is not None else None).astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('MEMORY_used', 'lower')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'Memória Ativa (MB) (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[1,1].plot(vm1_mem.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[1,1].plot(vm2_mem.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[1,1].set_title(title, fontweight='bold')
            axes[1,1].set_ylabel('MB')
            axes[1,1].legend()
            axes[1,1].grid(True, alpha=0.3)

    # --- SWAP ---
    vm1_swap_key = f'{vm1_label}_SWAP'
    vm2_swap_key = f'{vm2_label}_SWAP'
    if vm1_swap_key in parser.data and vm2_swap_key in parser.data:
        vm1_swap = parser.data[vm1_swap_key]
        vm2_swap = parser.data[vm2_swap_key]

        swpused_col = parser.get_column_by_candidates(vm1_swap_key, ['%swpused', 'swpused'])
        kbswpused_col = parser.get_column_by_candidates(vm1_swap_key, ['kbswpused', 'swpused'])

        if swpused_col:
            s1 = vm1_swap[swpused_col].dropna().astype(float)
            s2 = vm2_swap[swpused_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('SWAP_used', 'lower')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'Swap - % Utilizado (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[2,0].plot(vm1_swap.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[2,0].plot(vm2_swap.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[2,0].set_title(title, fontweight='bold')
            axes[2,0].set_ylabel('Percentual (%)')
            axes[2,0].legend()
            axes[2,0].grid(True, alpha=0.3)

        if kbswpused_col:
            s1 = vm1_swap[kbswpused_col].dropna().apply(lambda x: x/1024 if x is not None else None).astype(float)
            s2 = vm2_swap[kbswpused_col].dropna().apply(lambda x: x/1024 if x is not None else None).astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('SWAP_used', 'lower')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'Swap Utilizado (MB) (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[2,1].plot(vm1_swap.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[2,1].plot(vm2_swap.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[2,1].set_title(title, fontweight='bold')
            axes[2,1].set_ylabel('MB')
            axes[2,1].legend()
            axes[2,1].grid(True, alpha=0.3)

    # --- IO ---
    vm1_io_key = f'{vm1_label}_IO'
    vm2_io_key = f'{vm2_label}_IO'
    if vm1_io_key in parser.data and vm2_io_key in parser.data:
        vm1_io = parser.data[vm1_io_key]
        vm2_io = parser.data[vm2_io_key]

        tps_col = parser.get_column_by_candidates(vm1_io_key, ['tps'])
        bwrtn_col = parser.get_column_by_candidates(vm1_io_key, ['bwrtn', 'wrtn', 'wrtn/s', 'wrtn/s'])

        if tps_col:
            s1 = vm1_io[tps_col].dropna().astype(float)
            s2 = vm2_io[tps_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('IO_tps', 'higher')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'I/O - TPS (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[3,0].plot(vm1_io.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[3,0].plot(vm2_io.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[3,0].set_title(title, fontweight='bold')
            axes[3,0].set_ylabel('TPS')
            axes[3,0].legend()
            axes[3,0].grid(True, alpha=0.3)

        if bwrtn_col:
            s1 = vm1_io[bwrtn_col].dropna().astype(float)
            s2 = vm2_io[bwrtn_col].dropna().astype(float)
            m1 = mean_str(s1)
            m2 = mean_str(s2)
            pref = metric_preferences.get('IO_bytes', 'higher')
            pref_txt = "Mais alto melhor" if pref == 'higher' else "Mais baixo melhor"
            title = f'I/O - Bytes Escritos (por segundo) (Média VM1={m1}, VM2={m2} — {pref_txt})'
            axes[3,1].plot(vm1_io.index, s1, label=f'{vm1_label} (Média={m1})', linewidth=2, color=colors[vm1_label])
            axes[3,1].plot(vm2_io.index, s2, label=f'{vm2_label} (Média={m2})', linewidth=2, color=colors[vm2_label])
            axes[3,1].set_title(title, fontweight='bold')
            axes[3,1].set_ylabel('Bytes/s (ou valor correspondente)')
            axes[3,1].legend()
            axes[3,1].grid(True, alpha=0.3)

    # labels x
    for i in range(4):
        for j in range(2):
            axes[i,j].set_xlabel('Amostras')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig('series_temporais_comparacao.png', dpi=300, bbox_inches='tight')
    plt.show()

def print_stats(parser, vm1_label='VM1', vm2_label='VM2'):
    print("ESTATÍSTICAS RESUMIDAS")
    print("="*80)

    metric_map = [
        (f'{vm1_label}_CPU', '%user', 'CPU_User'),
        (f'{vm1_label}_CPU', '%system', 'CPU_System'),
        (f'{vm1_label}_MEMORY', '%memused', 'Memory_Used'),
        (f'{vm1_label}_SWAP', '%swpused', 'Swap_Used'),
        (f'{vm1_label}_IO', 'tps', 'IO_TPS'),
    ]

    for vm_section, col_cand, metric_name in metric_map:
        base = vm_section.split('_', 1)[1]
        vm1_key = f'{vm1_label}_{base}'
        vm2_key = f'{vm2_label}_{base}'
        if vm1_key in parser.data and vm2_key in parser.data:
            col1 = parser.get_column_by_candidates(vm1_key, [col_cand])
            col2 = parser.get_column_by_candidates(vm2_key, [col_cand])
            if col1 and col2:
                s1 = parser.data[vm1_key][col1].dropna().astype(float)
                s2 = parser.data[vm2_key][col2].dropna().astype(float)
                if len(s1) == 0 or len(s2) == 0:
                    continue
                print(f"\n{metric_name}:")
                print(f"  {vm1_label}: Média={s1.mean():.2f}, Max={s1.max():.2f}, Min={s1.min():.2f}")
                print(f"  {vm2_label}: Média={s2.mean():.2f}, Max={s2.max():.2f}, Min={s2.min():.2f}")
                print(f"  Diferença Média: {s1.mean() - s2.mean():.2f}")

# -----------------------
# Main
# -----------------------
def main():
    if len(sys.argv) >= 3:
        vm1_file = Path(sys.argv[1])
        vm2_file = Path(sys.argv[2])
    else:
        vm1_file = Path("vm1_report.sar")
        vm2_file = Path("vm2_report.sar")

    if not vm1_file.exists():
        print(f"Arquivo não encontrado: {vm1_file}")
        sys.exit(1)
    if not vm2_file.exists():
        print(f"Arquivo não encontrado: {vm2_file}")
        sys.exit(1)

    parser = SARDataParser2()

    print(f"Executando sar para {vm1_file} ...")
    out1 = run_sar_on_file(vm1_file)
    parser.parse_sar_output(out1, "VM1")

    print(f"Executando sar para {vm2_file} ...")
    out2 = run_sar_on_file(vm2_file)
    parser.parse_sar_output(out2, "VM2")

    print("\nDados carregados:", list(parser.data.keys()))

    print("\nGerando gráficos...")
    create_time_series_plots(parser, vm1_label='VM1', vm2_label='VM2')
    create_distribution_plots(parser, vm1_label='VM1', vm2_label='VM2')

    print("\nCalculando estatísticas...")
    print_stats(parser, vm1_label='VM1', vm2_label='VM2')

    print("\nConcluído. Gráfico salvo em 'series_temporais_comparacao.png'")

def create_distribution_plots(parser, vm1_label='VM1', vm2_label='VM2'):
    """
    Gera boxplot + histograma para cada métrica principal,
    comparando a distribuição entre VM1 e VM2.
    """

    import matplotlib.pyplot as plt

    metrics = [
        ('CPU', ['%user', '%system'], ['cpu_user', 'cpu_system']),
        ('MEMORY', ['%memused'], ['mem_used']),
        ('SWAP', ['%swpused'], ['swap_used']),
        ('IO', ['tps'], ['io_tps'])
    ]

    for section, col_candidates, names in metrics:
        vm1_key = f'{vm1_label}_{section}'
        vm2_key = f'{vm2_label}_{section}'
        if vm1_key not in parser.data or vm2_key not in parser.data:
            continue

        vm1_df = parser.data[vm1_key]
        vm2_df = parser.data[vm2_key]

        for col_cand, metric_name in zip(col_candidates, names):
            col1 = parser.get_column_by_candidates(vm1_key, [col_cand])
            col2 = parser.get_column_by_candidates(vm2_key, [col_cand])
            if not col1 or not col2:
                continue

            s1 = vm1_df[col1].dropna().astype(float)
            s2 = vm2_df[col2].dropna().astype(float)

            if len(s1) < 3 or len(s2) < 3:
                continue

            # ---------------- BOX PLOT ----------------
            plt.figure(figsize=(8,5))
            plt.boxplot([s1, s2], labels=[vm1_label, vm2_label], showmeans=True)
            plt.title(f"Distribuição - {metric_name.replace('_',' ').upper()}")
            plt.ylabel("Valor")
            plt.grid(alpha=0.3)
            plt.savefig(f"dist_{metric_name}_boxplot.png", dpi=300, bbox_inches='tight')
            plt.close()

            # ---------------- HISTOGRAMA ----------------
            plt.figure(figsize=(8,5))
            plt.hist(s1, bins=20, alpha=0.5, label=f'{vm1_label}')
            plt.hist(s2, bins=20, alpha=0.5, label=f'{vm2_label}')
            plt.title(f"Histograma - {metric_name.replace('_',' ').upper()}")
            plt.xlabel("Valor")
            plt.ylabel("Frequência")
            plt.legend()
            plt.grid(alpha=0.3)
            plt.savefig(f"dist_{metric_name}_hist.png", dpi=300, bbox_inches='tight')
            plt.close()


if __name__ == "__main__":
    main()

