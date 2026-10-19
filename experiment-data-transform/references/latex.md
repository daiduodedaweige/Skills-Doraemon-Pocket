# LaTeX 表格契约与示例

适用于含 `table`／`table*`、`tabular`、booktabs、`\textbf{}` 和 `\%` 的输入。读取整个文件，支持多个表格；不要用简单的按 `&` 全局拆分替代对转义、花括号和环境的识别。

保持表格环境、列定义、标题、标签、行名、列名、宏、行列顺序、间距设置和百分号转义。自定义宏（如 `\sourcefile`）须保留；仅当项目约定该宏必须指向新产物时更新路径。默认不扩展或删除宏。

单元格内 `\textbf{100.00\%}` 的数值是 100.00%，加粗不是数据。保留方法名加粗；按列更新数值加粗。列方向可从标题或用户描述确定；含糊时询问，不默认所有列越大越好。原表按展示值并列时，按展示精度判定并列。

## 输入范例

```tex
\begin{table}[htbp]
\centering
\caption{Overall comparison. Best values are bold, with ties included.}
\sourcefile{input_doc/compare_ex.tex}
\label{tab:overall-comparison}
\setlength{\tabcolsep}{3.4pt}
\begin{tabular}{lcccc}
\toprule
Method & FPV-Pass & Non-vac. & Non-triv. & Cover \\
\midrule
Direct LLM & 85.08\% & 99.32\% & \textbf{100.00\%} & 68.52\% \\
AssertLLM & 99.06\% & 89.62\% & 88.36\% & 89.47\% \\
PALM & 99.33\% & 91.17\% & 90.83\% & \textbf{94.25\%} \\
AutoAssert-style (TTLLM) & \textbf{100.00\%} & 92.46\% & 91.53\% & 93.72\% \\
\textbf{HiC-Verify} & \textbf{100.00\%} & \textbf{99.35\%} & \textbf{100.00\%} & 92.56\% \\
\bottomrule
\end{tabular}
\end{table}
```

描述示例：

> 生成一个假设合成场景，仅将 HiC-Verify 的 Cover 提高 2 个百分点，其余数值不变，更新最优值加粗。

处理结果：HiC-Verify 的 Cover 为 `\textbf{94.56\%}`；PALM 的 Cover 改为 `94.25\%`；其他数值、方法名加粗和结构不变。输出开头添加：

```tex
% data_kind: hypothetical-synthetic
% rule: HiC-Verify Cover +2 percentage points; all other values fixed.
% validation: deterministic scenario; not an observed experimental result.
```

“增加 2%”与“增加 2 个百分点”不同：92.56% 的相对增加 2% 是 94.4112%，显示 94.41%；增加 2 个百分点是 94.56%。语义含糊且会改变结果时澄清。

反例：仅给此表并要求“topK 从 3 改为 5，预测各指标”，不能拟合有依据的 GPR；表中无 topK 或配置对照，需请求逐次实验配置及结果，或明确的合成假设。表中 Non-vac.、Non-triv. 与 FPV-Pass 也不能仅凭列名认定分母相同或强加乘法关系。
