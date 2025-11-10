
# Tunning de Performance em Linux para Ambientes de Containers

Este repositório reúne todos os scripts utilizados no tutorial de otimização de performance para nós Linux rodando cargas conteinerizadas.  
Ele acompanha o passo a passo apresentado no artigo (a ser publicado em):  
**https://marllus.com/xxxx**

O objetivo do material não é apenas aplicar ajustes de performance, mas também **demonstrar como analisar métricas de sistema de forma correta**, especialmente em cenários de alta carga, onde **a média nem sempre representa bem o comportamento real**.  
No artigo, discutimos como **distribuições multimodais** podem tornar a média enganosa e por que, em determinados casos, a **mediana e os percentis** são indicadores melhores para entender a tendência dos dados — embora, neste caso específico, a média ainda tenha se mostrado representativa.

---

## 🚀 Conteúdo deste Repositório

| Arquivo / Script               | Função                                                                                   |
|-------------------------------|-------------------------------------------------------------------------------------------|
| `tune_node.sh`                | Aplica ajustes de performance no nó: BBR, Swappiness, THP e C-States.                     |
| `stress_test.sh`              | Script para gerar carga controlada e reproduzível no sistema.                             |
| `sar_visualize.py`            | Gera gráficos de séries temporais a partir dos relatórios do `sar`.                       |
| `sar_visualize_boxsplot.py`   | Cria **boxplots** para análise de distribuição e identificação de multimodalidade.        |
| `CV_metric_final.py`          | Calcula **média, mediana, p95, p99 e Coeficiente de Variação** para cada métrica coletada.|
| `cloud-config`                | Arquivo de provisionamento automático para replicar o ambiente de testes.                |
| `README.md`                   | Você está aqui.                                                                           |

---

## 📊 O que você vai aprender com este projeto

- Como rodar testes de carga reproduzíveis
- Como coletar métricas reais com `sar` (sysstat)
- Quando confiar (ou **não**) na **média**
- Como identificar **picos** e **distribuições multimodais** através de boxplots
- Como interpretar **mediana, p95 e p99** para análise de performance
- Como aplicar otimizações seguras e efetivas no kernel para workloads conteinerizados

---

## 🛠 Uso (Fluxo Recomendado)

1) Aplique otimizações no nó:
```bash
sudo ./tune_node.sh
````

2. Execute o teste de estresse:

```bash
./stress_test.sh
```

3. Colete e grave logs do `sar`.

4. Visualize gráficos:

```bash
python sar_visualize.py vm1_report.sar
python sar_visualize_boxsplot.py vm1_report.sar vm2_report.sar
```

5. Compare variações estatísticas:

```bash
python CV_metric_final.py vm1_report.sar vm2_report.sar
```

---

## 📝 Licença

Livre para uso e adaptação com crédito ao autor.

---

## 🌐 Artigo Explicando Todo o Processo

> Em breve: **[https://marllus.com/xxxx](https://marllus.com/xxxx)**

---


