# Stockfish Remote Proxy

Un proxy Python permettant d'exécuter Stockfish sur un serveur distant via SSH et de l'utiliser comme s'il était installé localement.    
Idéal pour utiliser la puissance de calcul d'un serveur dédié pour l'analyse d'échecs.

**Recommandation importante** : Lisez ce README complètement une première fois avant de commencer l'installation.

Cela vous évitera des erreurs et vous fera gagner du temps :)       
Il est volontairement exhaustif, si tout se passe bien l'installation se fera en moins de 30min.

## Fonctionnalités

- **Proxy transparent** : Utilise Stockfish distant comme s'il tournait en local
- **Communication UCI** : Support complet du protocole UCI (Universal Chess Interface)
- **Auto-configuration** : Configuration automatique optimisée selon les paramètres définis
- **Gestion d'état** : Gestion intelligente des commandes d'analyse (`go infinite`, `stop`)
- **Logging configurable** : Système de logs détaillé pour le debugging
- **Connexion sécurisée** : Utilise SSH avec authentification par clé privée
- **Synchronisation** : Attente des réponses UCI appropriées (`uciok`, `readyok`, `bestmove`)

## Prérequis

### Système local (Windows)

- **Python 3.x** : [Télécharger Python](https://www.python.org/downloads/)
    - Important : Cocher "Add Python to PATH" lors de l'installation
- **PuTTY** : [Télécharger PuTTY](https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html)
- **Clé SSH privée** au format PuTTY (`.ppk`)
    - Important : La clé ne doit **PAS** avoir de mot de passe (passphrase vide) **sinon plink en mode batch ne pourra pas l'utiliser !**

### Serveur distant (Debian-Ubuntu GNU/Linux)

- **Stockfish installé** :
- **Accès SSH configuré** avec authentification par clé

### Recommandations pour serveur distant

**Ressources minimales** :
- 4 cores CPU minimum pour un gain notable
- 8 GB RAM minimum pour analyses approfondies  
- Connexion stable avec latence < 50ms

### Documentation SSH
Pour la configuration SSH complète concernant l'échange de clefs publiques/privées : [Guide SSH Debian](https://wiki.debian.org/fr/SSH#Utilisation_de_cl.2BAOk-s_partag.2BAOk-es)

## Installation

### 1. Installation côté serveur distant (Debian/Ubuntu GNU Linux)

* Installation de Stockfish - ajoutez sudo devant si vous n'êtes pas root ou si avez choisi de faire tourner Stockfish avec un utilisateur dédié (ce qui est une très bonne idée !)
```bash
apt install stockfish
```

* Vérifier l'installation
```bash
stockfish
```
Devrait afficher le header de Stockfish avec sa version : "Stockfish 17.1 by the Stockfish developers"

Puis saisir `quit` pour sortir

* Vérifier le chemin d'installation
```bash
which stockfish
```

Généralement : /usr/games/stockfish

### 2. Configuration côté local (Windows)

#### Configuration SSH (PuTTY)

Création d'une clé sans mot de passe avec PuTTYgen :

1. Ouvrir PuTTYgen
2. Générer une nouvelle clé
3. **Laisser vide** le champ "Key passphrase"
4. Sauvegarder la clé privée (`.ppk`) et publique
5. Ajouter la clé publique sur le serveur distant

#### Récupérer les fichiers du projet

1. **Cloner ou télécharger** les fichiers du projet :

```bash
git clone https://github.com/deuza/proxy_stockfish.git
```

2. **Créer le fichier** `config.json` avec vos paramètres (voir plus loin !) :

```json
{
  "host": "votre-serveur.com", 
  "username": "votre-utilisateur", 
  "port": "22", 
  "key_file": "C:\\chemin\\vers\\votre\\cle.ppk",
  "plink_path": "C:\\Program Files\\PuTTY\\plink.exe", 
  "stockfish_command": "/usr/games/stockfish", 
  "logging_enabled": true, 
  
  "_comment_stockfish_config": "Options de configuration pour Stockfish",
  "sf_threads": 16, 
  "sf_hash": 8192,
  "sf_multipv": 1,
  "sf_ponder": true,
  
  "sf_options": {
    "Skill Level": 20,
    "UCI_ShowWDL": true
  }
}
```

##### Paramètres de configuration de base

| Paramètre | Description | Exemple |
|-----------|-------------|---------|
| `host` | Adresse IP ou hostname du serveur distant | `"mon-serveur.com"` |
| `username` | Nom de l'utilisateur distant | `"root"`, `pi` , `your-user` ... |
| `port` | Port SSH | `"22"` (port par défaut) |
| `key_file` | Le chemin de votre clef privée .ppk | `"C:\\Users\\USER\\.ssh\\id_rsa.ppk"` |
| `plink_path` | Le chemin du binaire `plink.exe` sous Windows | `"C:\\Program Files\\PuTTY\\plink.exe"` |
| `stockfish_command` | Le chemin du binaire `stockfish` sous Debian GNU/Linux | `"/usr/games/stockfish"` |
| `logging_enabled` | Activer/désactiver les logs | `true` ou `false` |

##### Options Stockfish avancées

| Paramètre | Description | Valeurs recommandées |
|-----------|-------------|---------------------|
| `sf_threads` | Nombre de threads CPU | Nombre de cores du serveur (ex: 16) |
| `sf_hash` | Taille du hash en MB | 50% de la RAM serveur (ex: 8192 = 8GB) |
| `sf_multipv` | Nombre de variantes analysées | 1 (mono), 3-5 (multi-variantes) |
| `sf_ponder` | Réflexion pendant tour adverse | `true` (évite les bugs de blocage) |
| `sf_options` | Options Stockfish personnalisées (optionnel) | Voir exemples ci-dessous |


#### Exemples de configurations optimisées

**Configurations typiques de Stockfish** :

- **Raspberry Pi 5** : 4 cores, 8GB RAM → sf_threads: 4, sf_hash: 4096
- **VPS moyen** : 8 cores, 16GB RAM → sf_threads: 8, sf_hash: 8192
- **Serveur dédié** : 16+ cores, 32+ GB RAM → sf_threads: 16, sf_hash: 16384

**Exemple de configuration pour Raspberry Pi 5 (4 cores, 8GB RAM) :**

```json
{
  "sf_threads": 4,
  "sf_hash": 4096,
  "sf_multipv": 1,
  "sf_options": {
    "Skill Level": 20
  }
}
```

#### Pour obtenir des chiffres précis concernant votre matériel et de votre installation :

- **Threads** = nombres de CPUs disponible via la commande :

```bash
nproc
```

- **Hash** = RAM/2 (le chiffre correspondant à la commande :

```bash
awk '/MemTotal/ {print int($2/2048)}' /proc/meminfo
```

La taille du `hash` va impacter directement votre mémoire, la commande ci dessus permet d'avoir la taille de **la mémoire disponible avec l'OS** en action et pas **la mémoire globale**, ce qui permettra à Stockfish de prendre son aise sans dégrader les performances de votre serveur en le faisant surchauffer.


### 3. Tests de validation

#### Test 1 : Connexion SSH avec plink

Tester la connexion SSH directement avec `plink.exe` :

```powershell
PS C:\> & 'C:\Program Files\PuTTY\plink.exe' -batch -i C:\chemin\vers\votre\cle.ppk -P 22 utilisateur@votre-serveur.com uname -a
```

**Résultat attendu (avec les caractéristiques de votre matériel)** :
```
Linux serveur 6.12.38+deb13-amd64 #1 SMP PREEMPT_DYNAMIC Debian 6.12.38-1 (2025-07-16) x86_64 GNU/Linux
```

Si ça fonctionne, alors `plink.exe` peut se connecter et la clé du serveur sera ajoutée dans votre fichier `.ssh\known_hosts`.

#### Test 2 : Script Python avec auto-configuration

Tester le script pour vérifier que tout fonctionne :

```powershell
PS C:\proxy_stockfish> python .\proxysf.py
```

**Session de test avec auto-configuration** :
```
Stockfish 17.1 by the Stockfish developers (see AUTHORS file)
isready
readyok
uci
id name Stockfish 17.1
id author the Stockfish developers (see AUTHORS file)
[... options UCI ...]
uciok
quit
```

Les logs `debug.log` devraient montrer la configuration automatique :
```
INFO - Initializing Stockfish with custom configuration...
INFO - Setting Stockfish threads to 16
INFO - Setting Stockfish hash to 8192MB
INFO - Disabling Stockfish Ponder mode
INFO - Stockfish initialization completed.
```

Si ces deux tests passent, vous pouvez créer l'exécutable.

### 4. Création de l'exécutable

1. **Installer PyInstaller** :
   ```bash
   pip install pyinstaller
   ```

2. **Créer l'exécutable** :
   ```bash
   pyinstaller --onefile --console proxysf.py
   ```

   L'exécutable sera créé dans le dossier `dist/proxy_sf.exe`

3. **Copier le fichier de configuration à côté de l'exe** :
   ```powershell
   PS C:\proxysf> cp .\config.json dist/
   ```

4. **Se déplacer dans le répertoire contenant l'exécutable et son fichier de configuration** :
   ```powershell
   PS C:\proxysf> cd dist/
   ```

### 5. Tests et manipulation du binaire

Pour tester manuellement l'exécutable, lancer `proxysf.exe` dans un terminal :

```
> proxysf.exe
> uci
id name Stockfish 17.1
id author the Stockfish developers
[... options UCI ...]
uciok

> isready
readyok

> quit
```

## Auto-configuration Stockfish

### Fonctionnement

Au démarrage, le proxy configure automatiquement Stockfish avec les paramètres optimaux définis dans `config.json` :

1. **Threads** : Utilise le nombre spécifié (`sf_threads`)
2. **Hash** : Alloue la mémoire spécifiée (`sf_hash`)  
3. **MultiPV** : Configure l'analyse multi-variantes (`sf_multipv`)
4. **Ponder** : Désactivé par défaut pour éviter les blocages
5. **Options custom** : Applique les options de `sf_options`

### Priorité des configurations

1. **Proxy** configure d'abord selon `config.json`
2. **GUI** peut ensuite reconfigurer (mais attention aux écrasements)
3. **Recommandation** : Laisser le proxy gérer les ressources et la GUI gérer le jeu

### Commandes UCI supportées

Le proxy transmet toutes les commandes UCI standard vers Stockfish distant :

- `uci` - Initialisation UCI
- `isready` - Vérification de disponibilité
- `position startpos` / `position fen <fen>` - Définition de position
- `go depth 15` / `go infinite` - Lancement d'analyse
- `stop` - Arrêt d'analyse
- `quit` - Fermeture

## Utilisation dans Arena Chess (par exemple)

### Configuration d'Arena

1. **Lancer Arena Chess**
2. **Aller dans** : `Engines` → `Install Engine`
3. **Sélectionner** : `proxy_stockfish.exe`
4. **Type** : `UCI Engine`
5. **Valider** la configuration

Arena utilisera alors votre Stockfish distant comme n'importe quel moteur local, automatiquement configuré avec les ressources optimales du serveur.

### Compatibilité autres GUI

Le proxy est compatible avec :
- **Arena Chess** 
- **Lucas Chess** 
- **Scid vs PC**
- **Chess Base**
- *Normalement tout logiciel supportant les moteurs UCI*

## Gestion des analyses infinies

Le proxy gère intelligemment les analyses infinies :
- Envoie automatiquement `stop` avant une nouvelle commande si l'engine analyse
- Met en queue la commande suivante
- Attend la réponse `bestmove` avant de continuer

## Logs et debugging

Avec `logging_enabled: true`, les logs sont sauvés dans `debug.log` :
- Commandes envoyées à Stockfish
- Réponses reçues
- Configuration automatique appliquée
- États internes du proxy
- Erreurs de connexion

**Exemple de log d'initialisation** :
```
2025-08-13 10:30:15,123 - INFO - Starting remote Stockfish wrapper.
2025-08-13 10:30:15,456 - INFO - Plink process started successfully.
2025-08-13 10:30:16,123 - INFO - Initializing Stockfish with custom configuration...
2025-08-13 10:30:16,125 - INFO - Setting Stockfish threads to 16
2025-08-13 10:30:16,127 - INFO - Setting Stockfish hash to 8192MB
2025-08-13 10:30:16,131 - INFO - Disabling Stockfish Ponder mode
2025-08-13 10:30:16,137 - INFO - Stockfish initialization completed.
```

## Résolution de problèmes

### Erreur de connexion SSH
- Vérifier les paramètres `host`, `username`, `port`
- S'assurer que la clef SSH est correcte et autorisée sur le serveur
- Tester la connexion manuellement avec PuTTY

### Stockfish non trouvé
- Vérifier le chemin dans `stockfish_command`
- S'assurer que Stockfish est installé sur le serveur
- Tester avec `which stockfish` ou `whereis stockfish` sur votre serveur GNU/Linux

### Plink non trouvé
- Vérifier le chemin dans `plink_path`
- Installer PuTTY si nécessaire
- Utiliser le chemin complet vers `plink.exe`

### Configuration non appliquée
- Vérifier la syntaxe du `config.json`
- Consulter `debug.log` pour les erreurs d'initialisation
- S'assurer que les valeurs sont dans les limites Stockfish

### Analyse bloquée ou emballement
- Le proxy envoie automatiquement `stop` si nécessaire
- En cas de blocage, `Ctrl+C` pour terminer
- Vérifier les logs pour identifier le problème

### Arret d'urgence

#### Côté serveur GNU/Linux

- Tuer les processus stockfish :
  
```bash
killall stockfish
```

- Puis vérifier :

```bash
ps aux | grep stockfish  # vérifier qu'il n'en reste plus
```

#### Côté Windows

- Via le *Gestionnaire des tâches* :      

Tuer tout les processus `proxysf.exe`

- Via *PowerShell* :       

```powershell
taskkill /f /im proxysf.exe
```

### Instances multiples

**Limitation importante** : Le proxy ne vérifie pas les instances multiples. 

En cas de lancement simultané (tournois avec plusieurs workers, tests multiples ...) plusieurs processus Stockfish peuvent s'accumuler côté serveur et consommer toute la RAM, le swap puis crasher.

**Prévention** :
- Utiliser une seule instance de proxy à la fois
- En cas de tournois, surveiller la consommation mémoire serveur avec `htop` (par ex)
- Nettoyer manuellement les processus avant relancement

## Architecture technique

```
[Interface UCI locale] 
        ↓
[proxysf.py]
        ↓ configuration (sécurisée par SSH)
[plink.exe] → [Serveur distant] → [Stockfish configuré]
        ↑                              ↓
[Réponses UCI] ← ← ← ← ← ← ← ← ← ← ← ← ←
```

## Distribution et sécurité

### Distribution

Pour distribuer ce projet :
1. **Code source sur GitHub** - transparence totale
2. **Instructions de compilation** - chacun compile son propre .exe

*Pas de binaire pré-compilé disponible volontairement, mais c'est facile à faire !*

### Implications au niveau sécurité d'un exécutable distribué

**Important** : Un .exe distribué doit légitimement susciter la méfiance, car en plus du logiciel original du code malveillant à pu être ajouté avant la compilation. 

C'est pour cette raison que j'ai fait le choix de ne pas fournir de binaire directement exécutable en plus du code source.

- Compiler vous-même depuis le code source
- Vérifier les checksums si vous téléchargez un .exe pré-compilé
- Scanner avec votre antivirus (à jour)
- Examiner le code source avant compilation

## Sécurité du proxy

- Utilise uniquement l'authentification par clé SSH, pas de password
- Pas de mot de passe en dur dans la configuration
- Connexion chiffrée via SSH
- Mode batch de plink (non-interactif)
- Configuration Stockfish limitée aux options standard UCI

## Limitations connues

### Version actuelle (plink)
- **Dépendant de la latence réseau** pour les réponses
- **Nécessite une connexion stable** au serveur
- **Nécessite suffisament de ressources dispo** sur le serveur pour utiliser pleinement Stockfish
- **Spécifique à Windows** (utilise plink.exe)
- **Une seule connexion SSH** : impossible de détecter dynamiquement les ressources serveur
- **Pas de gestion d'instances multiples** : possibilité d'emballement mémoire voir saturation, écritures dans le swap jusqu'à ce qu'il soit plein puis crash
- **Evitez une valeur de hash trop élevée** : fortes possibilité de saturation immédiate de la RAM, écritures dans le swap jusqu'à ce qu'il soit plein puis crash

### Philosophie KISS

Ce proxy privilégie la simplicité et la fiabilité. Les limitations ci-dessus sont documentées et des solutions manuelles sont proposées plutôt que de complexifier le code avec des mécanismes avancés de gestion d'instances, de parsing UCI, d'auto-configuration en fonction du serveur distant ou autre.

## TODO

Version full Python, permettant de s'affranchir de plink.exe et du format de clef propre à PuTTY en utilisant directement OpenSSH pour l'authentification.      
Ce qui permettrait logiquement de rendre ainsi le proxy fonctionnel sous macOS et les systèmes GNU/Linux.

## License

CC-0  
Projet open source - à adapter selon vos besoins.

---

**Note** : Ce proxy a été testé avec Stockfish 17.1 et PuTTY sur Windows 11.
