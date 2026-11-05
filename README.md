# EuroALM-X — première ébauche exécutable

Ce dossier contient une **preuve de concept pédagogique** d'aide à l'allocation actif-passif pour un assureur en euros. Il part de flux de passif et d'une courbe zéro fictifs, valorise les deux côtés du bilan, simule des chocs de taux parallèles sur un horizon d'un an, puis choisit une allocation sous contraintes. Il utilise uniquement la bibliothèque standard Python.

Il s'agit d'une première tranche du projet, pas d'un modèle réglementaire ni d'une recommandation d'investissement. **Aucune donnée de marché réelle, aucun taux de référence officiel, aucune estimation statistique de volatilité** ne sont encore intégrés. Les résultats numériques ne doivent donc pas être interprétés comme des prévisions.

## Lancer

Depuis ce dossier :

```powershell
python -m euroalm_mvp
python -m unittest discover -s tests -v
```

Variantes : `python -m euroalm_mvp --seed 7 --scenarios 3000 --step 0.05`. Un pas plus fin augmente fortement le nombre d'allocations testées. Le programme indique explicitement lorsqu'aucun portefeuille ne satisfait un objectif de rendement sur la grille choisie.

Avec les paramètres par défaut, le programme sélectionne `[20 %, 20 %, 20 %, 0 %, 40 %]` pour les seuils de 2 % et 3 % : rendement moyen simulé 3,64 %, écart de duration +0,04 an, ES99 de 0,0034 unité monétaire et couverture du paiement à un an de 3,40 fois. Le seuil de 4 % est infaisable sur cette grille. Ces chiffres illustrent uniquement le jeu de données fictif fourni.

## Ce que calcule le prototype, étape par étape

### 1. Courbe des taux zéro et actualisation

La courbe fournit un **taux zéro** `r(t)` pour chaque maturité `t`. Un paiement certain de 1 à la date `t` vaut aujourd'hui `exp(-r(t) × t)` dans la convention de capitalisation continue utilisée ici. Entre les nœuds de la courbe, le code interpole linéairement les taux zéro. Hors de l'intervalle disponible, il refuse l'extrapolation.

La courbe de démonstration vaut 2,0 % à 1 an, 2,3 % à 2 ans, 2,6 % à 5 ans, 2,9 % à 10 ans et 3,2 % à 20 ans. Ces chiffres sont inventés. **Un taux par, un rendement à l'échéance d'obligation et un taux zéro ne sont pas interchangeables** : lorsqu'une source publique sera branchée, il faudra vérifier la nature exacte de chaque série et, si nécessaire, construire les taux zéro par bootstrap avant de les utiliser ici.

### 2. Passifs, obligations et surplus

Les passifs sont quatre paiements hypothétiques : 6 à 1 an, 20 à 5 ans, 35 à 10 ans et 55 à 20 ans. Leur valeur initiale est la somme des paiements actualisés. Les actifs initiaux valent 100 et peuvent être placés en cash ou dans quatre obligations zéro coupon échéant à 2, 5, 10 et 20 ans. Une obligation zéro coupon paie son nominal une seule fois à l'échéance ; son prix initial est le nominal multiplié par le facteur d'actualisation.

Le **surplus** est `valeur des actifs − valeur des passifs`. À un an, on valorise les obligations et les passifs encore en vie avec la courbe choquée, puis on retire le paiement de passif dû à un an des actifs. Le cash initial gagne le taux court fixé au départ. On suppose qu'il n'y a pas de défaut, de frais, d'impôt, de rachat, de réinvestissement ni de réallocation pendant l'année.

### 3. Scénarios de taux et risque du surplus

Le programme génère 2 000 chocs **parallèles** de taux à l'aide d'une loi normale centrée, avec écart type hypothétique de 75 points de base, et une graine fixe pour reproduire l'exemple. Le même choc s'applique à toutes les maturités. Ces scénarios sont une convention d'exercice : ils ne sont ni des observations historiques, ni une calibration validée.

Pour chaque scénario, la perte est la différence entre le surplus à un an sous la courbe inchangée et le surplus à un an sous la courbe choquée. Cette définition mesure **l'effet du choc de taux** sur le surplus ; elle n'est pas la perte comptable totale de l'assureur. Une perte positive signifie que le choc réduit le surplus.

L'**Expected Shortfall à 99 %**, ou ES99, est la moyenne de la tranche des 1 % de pertes les plus fortes. Pour un échantillon discret, le code prend la fraction nécessaire de l'observation à la frontière. L'ES est ici une mesure **empirique et conditionnelle aux scénarios choisis** ; elle peut changer lorsque la distribution des scénarios change. L'affichage garde quatre décimales : une valeur proche de zéro ne signifie pas une absence de risque. Dans cette démonstration, un portefeuille peut presque neutraliser les chocs parallèles tout en restant exposé à des déformations de courbe, au crédit et à la liquidité réelle.

### 4. Contraintes d'allocation

Les poids sont positifs ou nuls et totalisent 100 % : pas de vente à découvert ni de levier. Le cash représente au moins 8 % des actifs et doit aussi couvrir intégralement le paiement de passif à un an, intérêts inclus. C'est un test de liquidité **à une seule date**, pas encore une projection complète des flux ni une règle réglementaire de réserve de cash.

La **duration** d'une obligation zéro coupon sous cette convention est sa maturité. La sensibilité monétaire du passif est la somme `t × valeur actuelle du flux à t`. L'écart contrôlé est `(duration monétaire des actifs − duration monétaire des passifs) / actifs initiaux`, en années. Il est borné en valeur absolue à 2 ans. On évite ainsi de comparer simplement `D_actifs − D_passifs` lorsque les valeurs d'actif et de passif diffèrent. Cette protection reste **locale** : un écart faible ne garantit pas une bonne couverture lors d'un grand choc ou d'une déformation non parallèle de la courbe.

Le rendement de l'actif à un an est la moyenne, sur les scénarios fictifs, des valeurs finales des actifs rapportées au capital initial. Le programme résout séparément des seuils de 2 %, 3 % et 4 %. Ce **rendement moyen simulé** n'est ni promis ni estimé sur des données historiques ; un seuil peut être infaisable.

### 5. Recherche de portefeuille

Le moteur énumère les poids par pas de 10 % (`--step 0.1`) et calcule l'ES99 pour chaque portefeuille admissible. Il choisit celui dont l'ES99 est le plus petit. C'est une **optimisation sur grille**, donc le résultat est le meilleur *sur cette grille*, pas un optimum continu garanti. Avec cinq actifs et un pas de 10 %, il existe 1 001 combinaisons avant application des contraintes. Le choix d'une grille rend la logique inspectable et évite d'ajouter immédiatement un solveur externe.

## Architecture du code

- `euroalm_mvp/core.py` : courbe, passifs, valorisation, scénarios, ES, contraintes et optimisation ; les unités et hypothèses sont indiquées dans les docstrings.
- `euroalm_mvp/__main__.py` : interface en ligne de commande et restitution des résultats.
- `tests/test_core.py` : vérifications financières simples et cas limites importants.

Les objets de domaine (`Curve`, `Liability`, `PortfolioResult`) sont des dataclasses immuables. Une graine aléatoire fixe rend les résultats reproductibles. Les validations empêchent notamment une extrapolation silencieuse et les paramètres incohérents.

## Limites à connaître avant d'en parler sur un CV

Le prototype emploie une courbe inventée, des passifs inventés, des obligations zéro coupon et des chocs gaussiens parallèles inventés. Il n'inclut pas encore la récupération de données BCE ou Bundesbank, le bootstrap d'instruments de marché, la comparaison à une courbe officielle, des obligations à coupons, des ETF, du risque de crédit ou de change, des scénarios asymétriques, un calcul d'ES validé hors échantillon, plusieurs dates de liquidité, ni un surrogate de machine learning. Il n'implémente pas Solvabilité II.

Une formulation CV honnête **après exécution et vérification locale** serait : « Développement d'un prototype Python d'optimisation actif-passif : valorisation par courbe zéro, simulation de chocs de taux, calcul de l'ES99 du surplus et allocation sous contraintes de duration, rendement et liquidité. » Ajouter « sur données synthétiques » si l'espace le permet.

## Suite logique

1. Importer une courbe publique avec date, unités, définition des taux, contrôle des trous et provenance explicite.
2. Construire une courbe zéro à partir de cotations adaptées ; comparer les résultats à une courbe zéro officielle de référence lorsque les univers sont compatibles.
3. Ajouter des obligations à coupons et des flux de passif plus denses, puis vérifier les besoins de cash à plusieurs dates.
4. Introduire les chocs de pente et de courbure, des scénarios fondés sur des données observées et des tests de robustesse.
5. Passer à une optimisation continue ou scénarisée après avoir stabilisé les définitions financières ; étudier un ETF, puis des couvertures bornées.

Chaque étape devra conserver les mêmes conventions de taux, de temps et de flux dans la valorisation et dans les scénarios. Le notebook Python antérieur peut servir de point de départ technique **après vérification de la nature de ses taux d'entrée**.
