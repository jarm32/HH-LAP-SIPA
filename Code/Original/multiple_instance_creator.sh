#!/bin/bash

mkdir -p problems/

number_competences=6

for surplus in 30
#0 30 60
do
	for p_dep in 50 
		#10 30 50
	do
		for most_important in 1
		do
			mkdir -p "problems/$surplus/$p_dep/$most_important"
			python instance_creator.py "problems/$surplus/$p_dep/$most_important" 100 100 10 $surplus $p_dep $number_competences $most_important
		done
	done
done
