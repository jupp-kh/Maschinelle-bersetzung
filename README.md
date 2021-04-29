# Maschinelle Übersetzung

# Vorlesungtermine 

|Datum  |Thema    	|
|-------|------   	|
|13.04  |Metriken 	|  
|27.04  |		|
|04.05  |		|	
|(!)    |		|
|11.05  |		|
|01.06  |		|	
|15.06  |		| 
|06.07  |		|
|20.07  |		|

# Abgabetermine

| Thema | Deadline |Abgabe commitNr| geschafft |
| - | ----- | - | - |
|Metriken|26.04|2e6ca3e0|:heavy_check_mark:|
|Vokabular und Subword Units|-|-|-|
|Feed Forward Netzwerke|-|-|-|
|Suche|-|-|-|
|Rekurrente Neuronale Netzwerke|-|-|-|
|Blatt 6|-|-|-|



# Aufgabe 1 - Metriken 

In dieser Übungsblatt geht es darum die Metriken WER, PER und BLEU zu verstehen
Ein Programm zu schreiben welches diese für eine gegebene Menge von Referenz-Hypothese Paaren berechnet. 
Gemeint ist damit die Evaluation von Hypothesen durch den Vergleich mit einer oder mehreren Referenzenübersetzungen.

# Aufgabe 2 - Vokabular und Subword Units

Auf dem zweiten Blatt geht es um die Implementierung des byte pair encoding algorithmus. Wir sollen ein Programm schreiben, das Folgendes kann:
    - anhand einer gegebenen Anzahl von Zusammenzug-Operationen sowie Trainingsdaten eine BPE Zerlegung zu lernen.
    - erlernte BPE Operationen auf Text anzuwenden.
    - die BPE Zerlegung rückgängig zu machen.
Darüber hinaus erstellen wir eine Klasse Dictionary, die verwendet wird, um das Vokabular aus einem gegebenen Text/einer gegebenen Datei zu behalten. Der letzte Teil dieses Blattes beschäftigt sich mit der Weiterverarbeitung von Daten - dazu soll eine Funktion zur Erzeugung von "Batches" entwickelt werden.
