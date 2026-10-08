# Build main.pdf: regenerate the tables, then pdflatex + bibtex. Run `make` in paper/.
main.pdf: main.tex refs.bib generated/main_table.tex generated/ablation_table.tex
	pdflatex -interaction=nonstopmode -halt-on-error main.tex
	bibtex main
	pdflatex -interaction=nonstopmode -halt-on-error main.tex
	pdflatex -interaction=nonstopmode -halt-on-error main.tex

generated/%.tex: ../results/m13_tables.md tables.py
	cd .. && python paper/tables.py

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.pdf

.PHONY: clean
