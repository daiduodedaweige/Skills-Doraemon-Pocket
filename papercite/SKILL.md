---
name: papercite
description: Read supplied academic papers and a writing objective, then create one file with verified references, complete paired Chinese and English thesis-ready prose, and plain-language explanations of the citations. Use for source-grounded bilingual academic writing, not standalone translation.
---

# Paper-grounded bilingual writing

Turn one or more papers plus the user's requested claim or section purpose into **one saved file**. The normal deliverable is Markdown; follow a user-specified path, format, citation style, or language order when given. Otherwise, save it near the relevant manuscript or source papers under a descriptive name. Do not silently edit the manuscript itself.

Provide **both a complete Chinese version and a complete English version of every thesis-ready academic passage** in that file. The language of the user's request, manuscript, or source papers does not by itself justify omitting either version. If the requested writing spans multiple paragraphs or subsections, make the Chinese and English versions correspond paragraph by paragraph or subsection by subsection.

## Ground the writing

1. Read the supplied papers themselves. For PDFs, extract searchable text and inspect the relevant pages or tables when extraction is ambiguous; for other formats, use an appropriate parser. Existing notes can help locate passages but do not replace the papers as evidence.
2. Verify each paper's authors, title, year, venue, and DOI or other identifier from its front matter or publisher record. Read the sections that support the requested point, including methods, evaluation, and limitations where relevant. Record section or page anchors for important claims. Do not invent missing bibliographic fields.
3. If the requested paragraph discusses the user's own method, inspect available project material just enough to verify its terminology, scope, and status. Distinguish a proposed design or planned sample from an implemented or measured result. If such context is unavailable, write at the level the evidence supports and avoid made-up project specifics.

## Compose the file

Include these parts in one file:

1. **参考文献 / References:** Numbered entries in the user's required style, or a consistent standard style if none is supplied. Keep the original publication titles; include only verified identifiers.
2. **中文学术表述 / Chinese academic prose:** Complete, coherent prose suitable for direct use in a thesis or paper. Tie each cited prior-work claim to the relevant reference number, preferably with a section or page anchor when useful. Explain how the cited work informs the user's choice, what differs in task or setting, and why the user's approach follows.
3. **英文学术表述 / English academic prose:** A complete, faithful English counterpart suitable for direct use in a thesis or paper. Preserve all substantive claims, reasoning, qualifications, numerical details, and reference numbers from the Chinese version. Use established technical terms consistently and natural academic English; it need not be a literal sentence-by-sentence translation. Do not replace either academic version with a title, shortened summary, outline, or plain-language explanation.
4. **通俗说明 / Plain-language purpose:** Brief Chinese and English explanations of why each paper is cited and what the combined citations justify.

Paraphrase rather than copy long passages. Separate what a paper actually demonstrates from the writer's inference about the user's design choice. Never imply that the papers directly endorse, implement, or evaluate the user's specific framework unless they do. Where approaches differ, say so precisely without disparaging the cited work. Cite source claims close to the claims rather than only at a paragraph's end.

## Check before handing off

Reopen the saved file. Confirm it contains all four parts and every academic passage has complete Chinese and English counterparts. Compare them for the same claims, reasoning, qualifications, numerical details, citation numbers, and strength of claim; complete any missing or abbreviated counterpart before handing off. Confirm citation numbers resolve to the reference list, and any counts, method details, section anchors, and bibliographic fields match the papers or inspected project material. Flag inaccessible sources or unresolved metadata explicitly instead of filling gaps by guesswork. Return the file path and a short note that it contains both Chinese and English academic prose.
