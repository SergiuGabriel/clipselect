# Long Film score

Compares the app's Long Film with the owner's finished films, part by part (selections found / right, order, length).
Needs his pairs (selects XML + finished long film XML of the same wedding) in a folder: MMM_PAIRS=/path python3 run_score.py
Pairs used to build v3.4.0: selectie_madalina_si_radu.xml + Madalina_si_Radu_-_The_Movie.xml,
selectie_4_iulie_de_test.xml + Alexandra_si_Vlad_-_The_Movie.xml (part boundaries of his films are in score.CASES).
Every change to longfilm.build_film must keep or raise this score on BOTH weddings.
