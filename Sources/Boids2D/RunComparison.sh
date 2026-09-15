#!/bin/sh
# POSIX shell runner: prepare current Release binaries, then validate and compare witnesses.
set -eu
export LC_ALL=C

usage() {
    cat <<'HELP'
Usage: RunComparison.sh [--wait] [--prepare-only]
                        [--warmups N] [--runs N] [--output PATH]

  --wait          Attendre Entree apres verification des executables.
  --prepare-only  Compiler et verifier sans lancer le benchmark.
  --warmups N     Tours d echauffement : multiple de 6, defaut 6.
  --runs N        Tours mesures : multiple de 6, minimum 6, defaut 12.
  --output PATH   Un seul rapport texte .log (Baselines par defaut).
HELP
}
fail() { printf '%s\n' "$*" >&2; exit 1; }
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
root=$(CDPATH= cd -- "$source_dir/../../.." && pwd -P)
build_dir="$root/.silex/benchmarks/boids-comparison"
silex=${SILEX_BIN:-"$root/Silex/Toolchain/zig-out/bin/silex"}
cxx=${CXX:-clang++}
warmups=6
runs=12
wait_for_user=no
prepare_only=no
output=
while [ "$#" -gt 0 ]; do
    case $1 in
        --help|-h) usage; exit 0 ;;
        --wait) wait_for_user=yes; shift ;;
        --prepare-only) prepare_only=yes; shift ;;
        --warmups|--runs|--output)
            [ "$#" -ge 2 ] || fail "Valeur manquante pour $1"
            case $1 in
                --warmups) warmups=$2 ;;
                --runs) runs=$2 ;;
                --output) output=$2 ;;
            esac
            shift 2 ;;
        *) fail "Option inconnue : $1" ;;
    esac
done
# Canonical decimal integers keep shell arithmetic portable, including leading zeroes.
for number in "$warmups" "$runs"; do
    case $number in ''|*[!0-9]*) fail 'Nombre de tours invalide' ;; esac
    [ "${#number}" -le 6 ] || fail 'Nombre de tours trop grand'
done
warmups=$(printf '%s\n' "$warmups" | awk '{printf "%d", $1}')
runs=$(printf '%s\n' "$runs" | awk '{printf "%d", $1}')
[ $((warmups % 6)) -eq 0 ] && [ "$runs" -ge 6 ] && [ $((runs % 6)) -eq 0 ] || fail 'Echauffements et mesures : multiples de 6 ; au moins 6 mesures.'
for tool in awk git mktemp cmake shadercross cmp; do command -v "$tool" >/dev/null || fail "Outil requis : $tool"; done
if command -v sha256sum >/dev/null; then sha_tool=sha256sum
elif command -v shasum >/dev/null; then sha_tool=shasum
else fail 'sha256sum ou shasum est requis'; fi
hash_file() {
    [ -f "$1" ] || fail "Fichier absent : $1"
    if [ "$sha_tool" = sha256sum ]; then
        hash_output=$(sha256sum "$1") || fail "Lecture impossible : $1"
    else
        hash_output=$(shasum -a 256 "$1") || fail "Lecture impossible : $1"
    fi
    printf '%s\n' "$hash_output" | awk '{print $1}'
}
silex=$(command -v "$silex") || fail 'Compilateur Silex absent : lancer ./silex-dev build ou definir SILEX_BIN.'
cxx=$(command -v "$cxx") || fail 'Clang++ est requis pour la variante C++.'
case $silex in /*) ;; *) silex="$PWD/$silex" ;; esac
case $cxx in /*) ;; *) cxx="$PWD/$cxx" ;; esac
case $output in ''|/*) ;; *) output="$PWD/$output" ;; esac
scratch=$(mktemp -d "${TMPDIR:-/tmp}/silex-boids.XXXXXX")
report_owned=no
finished=no
cleanup() {
    result=$?
    trap - 0 HUP INT TERM
    if [ "$report_owned" = yes ] && [ "$finished" = no ]; then
        {
            cat "$scratch/header"
            printf '\nCAPTURE INVALIDE OU INTERROMPUE (code %s)\n' "$result"
            printf 'Aucune comparaison de performances validee.\n\n'
            [ ! -f "$scratch/failure" ] || cat "$scratch/failure"
            printf '\nPassages valides avant arret :\n'
            awk -F '\t' '
                BEGIN {label[0]="Silex/Natif";label[1]="Silex/LLVM";label[2]="C++/Clang";printf "%-12s %5s %8s %-18s %14s\n","Phase","Tour","Position","Variante","FPS"}
                {printf "%-12s %5s %8s %-18s %14s\n",$1,$2,$3,label[$4],$5}
            ' "$scratch/samples"
        } > "$output"
        printf '\nRapport partiel : %s\n' "$output" >&2
    fi
    rm -rf -- "$scratch"
    exit "$result"
}
trap cleanup 0
trap 'exit 130' INT
trap 'exit 129' HUP
trap 'exit 143' TERM
if ! "$cxx" --version > "$scratch/cxx-version" 2>&1; then
    if [ "$(uname -s)" = Darwin ] && [ -z "${CXX:-}" ] && [ -z "${DEVELOPER_DIR:-}" ] &&
        [ -x /Library/Developer/CommandLineTools/usr/bin/clang++ ]; then
        export DEVELOPER_DIR=/Library/Developer/CommandLineTools
        cxx="$DEVELOPER_DIR/usr/bin/clang++"
        printf 'Clang Xcode indisponible ; utilisation des Command Line Tools.\n'
        "$cxx" --version > "$scratch/cxx-version" 2>&1 || { cat "$scratch/cxx-version" >&2; fail 'Clang indisponible'; }
    else
        cat "$scratch/cxx-version" >&2
        fail 'Clang indisponible'
    fi
fi
awk 'tolower($0) ~ /clang/ {found=1} END {exit !found}' "$scratch/cxx-version" || fail 'La variante C++ requiert Clang.'
# Keep one current CMake build and three executables, not a directory per run.
# All Silex source compilation happens at the shared workspace root.
mkdir -p "$build_dir"
executable_for() {
    case $1 in
        0) printf '%s/native\n' "$build_dir" ;;
        1) printf '%s/llvm\n' "$build_dir" ;;
        2) printf '%s/cpp/BoidsCppArchitectural\n' "$build_dir" ;;
    esac
}
snapshot_sources() {
    for input in "$silex" "$cxx" "$(command -v shadercross)" \
        "$source_dir/RunComparison.sh" "$source_dir/Silex.sx" \
        "$source_dir/Cpp/CMakeLists.txt" "$source_dir/Cpp/Sources/Architectural.cpp" \
        "$root/Packages/GFX.Scene2D/Shaders/Drawing.hlsl"; do
        digest=$(hash_file "$input")
        printf '%s\t%s\n' "$input" "$digest"
    done
    for repository in "$root/Silex" "$root/Silex-Benchmarks" "$root"/Packages/*; do
        [ -e "$repository/.git" ] || continue
        revision=$(git -C "$repository" rev-parse HEAD)
        printf '%s\t%s\n' "$repository" "$revision"
        # Preserve exact tracked local edits instead of requiring unrelated commits.
        git -C "$repository" diff --binary HEAD -- > "$scratch/diff"
        digest=$(hash_file "$scratch/diff")
        printf 'working-tree\t%s\n' "$digest"
        git -C "$repository" ls-files --others --exclude-standard -- '*.sx' '*.json' '*.hlsl' > "$scratch/untracked"
        while IFS= read -r input; do
            digest=$(hash_file "$repository/$input")
            printf '%s/%s\t%s\n' "$repository" "$input" "$digest"
        done < "$scratch/untracked"
    done
}
snapshot_sources > "$scratch/sources"
printf 'Preparation Silex/Natif (Release)...\n'
(cd -- "$root" && "$silex" compile "$source_dir/Silex.sx" --backend native --release -o "$(executable_for 0)")
printf 'Preparation Silex/LLVM (Release)...\n'
(cd -- "$root" && "$silex" compile "$source_dir/Silex.sx" --backend llvm --release -o "$(executable_for 1)")
printf 'Preparation C++/Clang (Release)...\n'
set -- -S "$source_dir/Cpp" -B "$build_dir/cpp" \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER="$cxx" \
    -DCMAKE_CXX_FLAGS= '-DCMAKE_CXX_FLAGS_RELEASE=-O3 -DNDEBUG'
if [ "$(uname -s)" = Darwin ]; then
    sdk=$(xcrun --sdk macosx --show-sdk-path)
    set -- "$@" "-DCMAKE_OSX_SYSROOT=$sdk"
fi
cmake "$@"
cmake --build "$build_dir/cpp" --config Release --parallel 4
snapshot_sources > "$scratch/current"
cmp -s "$scratch/sources" "$scratch/current" || fail 'Sources ou outils modifies pendant la preparation : relancer la comparaison.'
: > "$scratch/files"
for witness in 0 1 2; do
    binary=$(executable_for "$witness")
    [ -x "$binary" ] || fail "Executable absent : $binary"
    digest=$(hash_file "$binary")
    printf '%s\t%s\n' "$binary" "$digest" >> "$scratch/files"
done
for input in "$build_dir/cpp/CMakeCache.txt" "$build_dir/cpp/Shaders/"*; do
    digest=$(hash_file "$input")
    printf '%s\t%s\n' "$input" "$digest" >> "$scratch/files"
done
cat "$scratch/sources" "$scratch/files" > "$scratch/seal"
config_hash=$(hash_file "$scratch/seal")
tab=$(printf '\t')
verify() {
    snapshot_sources > "$scratch/current"
    cmp -s "$scratch/sources" "$scratch/current" || fail 'Sources ou outils modifies : relancer la comparaison.'
    while IFS="$tab" read -r input expected; do
        [ "$(hash_file "$input")" = "$expected" ] || fail "Entree modifiee : $input"
    done < "$scratch/files"
}
verify
printf 'Comparaison : Silex/Natif, Silex/LLVM, C++/Clang. Executables verifies.\n'
printf '4000 boids x 480 frames ; %s echauffements + %s mesures par variante.\n' "$warmups" "$runs"
[ "$prepare_only" = no ] || exit 0
if [ "$wait_for_user" = yes ]; then
    printf '\nLaisse la machine au calme, puis appuie sur Entree : '
    IFS= read -r answer || fail 'Comparaison annulee avant lancement.'
fi
verify
case $(uname -s) in Darwin) os=macos ;; Linux) os=linux ;; MINGW*|MSYS*|CYGWIN*) os=windows ;; *) os=$(uname -s | tr '[:upper:]' '[:lower:]') ;; esac
case $(uname -m) in arm64|aarch64) arch=arm64 ;; x86_64|amd64|AMD64) arch=x64 ;; *) arch=$(uname -m) ;; esac
platform="$os-$arch"
[ -n "$output" ] || output="$source_dir/Baselines/$(date '+%Y-%m-%d-%H%M%S')-$platform.log"
mkdir -p -- "$(dirname -- "$output")"
# Refuse clobbering even if another runner creates this name at the same time.
(set -C; : > "$output") 2>/dev/null || fail "Capture deja existante : $output"
: > "$scratch/samples"
: > "$scratch/reference"
{
    printf 'BOIDS - COMPARAISON FPS\n\n'
    printf 'Date       : %s\nPlateforme : %s\n' "$(date '+%Y-%m-%d %H:%M:%S %z')" "$platform"
    printf 'Charge     : 4000 boids x 480 frames - Release\n'
    printf 'Passages   : %s echauffements + %s mesures par variante\n' "$warmups" "$runs"
} > "$scratch/header"
report_owned=yes
cat > "$scratch/validate.awk" <<'AWK_VALIDATE'
function bad(message) { print message > "/dev/stderr"; exit 1 }
function abs(x) { return x < 0 ? -x : x }
function finite(value) { return value ~ /^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$/ && tolower(sprintf("%.17g", value+0)) !~ /inf|nan/ }
FILENAME == reference { ref[$1]=$2; has_reference=1; next }
$1 == prefix {
    witnesses++
    for (i=2; i<=NF; i++) {
        if (split($i, pair, "=") != 2 || pair[1] in data) duplicate=1
        data[pair[1]]=pair[2]
    }
}
END {
    if (witnesses != 1 || duplicate) bad("Temoin absent, duplique ou mal forme")
    if (!finite(data["count"]) || data["count"]+0 != 4000 || !finite(data["frames"]) || data["frames"]+0 != 480) bad("Charge invalide")
    if (!finite(data["fixed_delta"]) || abs(data["fixed_delta"]-1/60)>0.0000001 || data["state_step"] != 4) bad("Pas de simulation invalide")
    if (data["present"] != "immediate") bad("Presentation invalide")
    if (split(data["window"], dim, "x") != 2 || !finite(dim[1]) || !finite(dim[2]) || dim[1]+0 != 960 || dim[2]+0 != 640) bad("Dimensions invalides")
    if (split(data["pixels"], pixels, "x") != 2 || !finite(pixels[1]) || !finite(pixels[2]) || pixels[1]+0<=0 || pixels[2]+0<=0) bad("Dimensions physiques invalides")
    if (!finite(data["scale"]) || !finite(data["density"]) || data["scale"]+0<=0 || data["density"]+0<=0) bad("Echelle invalide")
    if (!finite(data["fps"]) || data["fps"]+0<=0) bad("FPS invalides")
    n=split("initial_px initial_py initial_vx initial_vy initial_p2 initial_v2 state_px state_py state_vx state_vy state_p2 state_v2", keys, " ")
    for (i=1; i<=n; i++) {
        key=keys[i]
        if (!finite(data[key])) bad("Etat non fini ou incomplet : " key)
        if (has_reference) {
            a=data[key]+0; b=ref[key]+0; largest=abs(a)>abs(b)?abs(a):abs(b)
            if (abs(a-b)>0.05+largest*0.00002) bad("Etat divergent : " key)
        }
    }
    if (has_reference) {
        split(ref["pixels"], rp, "x")
        if (pixels[1]+0 != rp[1]+0 || pixels[2]+0 != rp[2]+0 || data["scale"]+0 != ref["scale"]+0 || data["density"]+0 != ref["density"]+0) bad("Affichage divergent")
        if (index_id != 2) {
            for (key in ref) if (key != "fps" && ("x" data[key]) != ("x" ref[key])) bad("Etat Silex divergent : " key)
            for (key in data) if (key != "fps" && !(key in ref)) bad("Champ Silex inattendu : " key)
        }
    } else {
        for (key in data) print key, data[key] > reference
        close(reference)
    }
    print data["fps"]
}
AWK_VALIDATE
cat > "$scratch/report.awk" <<'AWK_REPORT'
function abs(x) { return x<0?-x:x }
function median(values, count,    sorted,i,j,v) {
    for (i=1;i<=count;i++) sorted[i]=values[i]
    for (i=2;i<=count;i++) { v=sorted[i];j=i-1;while(j>0 && sorted[j]>v){sorted[j+1]=sorted[j];j--}sorted[j+1]=v }
    return count%2?sorted[(count+1)/2]:(sorted[count/2]+sorted[count/2+1])/2
}
function summary(id,    i,count,total,variance,lo,hi,med,mad,slope,denom,center,drift,shift,values,dev,left,right) {
    count=n[id];lo=sample[id,1];hi=lo
    for(i=1;i<=count;i++){values[i]=sample[id,i];total+=values[i];if(values[i]<lo)lo=values[i];if(values[i]>hi)hi=values[i]}
    mean[id]=total/count;med=median(values,count);center=(count-1)/2
    for(i=1;i<=count;i++){variance+=(values[i]-mean[id])^2;dev[i]=abs(values[i]-med);slope+=(i-1-center)*values[i];denom+=(i-1-center)^2;if(i<=count/2)left[i]=values[i];else right[i-count/2]=values[i]}
    mad=median(dev,count);drift=slope/denom*(count-1)/med;shift=(median(right,count/2)-median(left,count/2))/med
    if(mad/med>0.01 || (hi-lo)/med>0.04 || abs(drift)>0.01 || abs(shift)>0.01) unstable=1
    printf "%-18s %12.3f %12.3f %12.3f %12.3f\n",label[id],mean[id],lo,hi,sqrt(variance/count)
}
function gap(a,b) { printf "%-18s %-18s %+12.3f %+11.2f %%\n",label[a],label[b],mean[a]-mean[b],100*(mean[a]/mean[b]-1) }
BEGIN { FS="\t";label[0]="Silex/Natif";label[1]="Silex/LLVM";label[2]="C++/Clang";short[0]="N";short[1]="L";short[2]="C" }
{
    phase[$2]=$1;value[$2,$4]=$5;order[$2]=order[$2] (order[$2]!=""?">":"") short[$4]
    if($2>last)last=$2
    if($1=="Mesure")sample[$4,++n[$4]]=$5+0
}
END {
    for(i=0;i<3;i++)if(n[i]<6 || n[i]!=runs){print "Capture incomplete" > "/dev/stderr";exit 1}
    printf "\n%-18s %12s %12s %12s %12s\n","Variante","FPS moyens","FPS min","FPS max","Ecart-type"
    print "-----------------------------------------------------------------------"
    for(id=0;id<3;id++)summary(id)
    print "\nMoyennes hors echauffements ; min/max et dispersion entre passages, pas entre frames."
    print "\nECARTS ENTRE VARIANTES"
    printf "\n%-18s %-18s %12s %13s\n","Variante","Reference","Ecart FPS","Ecart relatif"
    print "-----------------------------------------------------------------------"
    gap(1,0);gap(0,2);gap(1,2)
    print "\nEcart relatif = (FPS moyens variante / FPS moyens reference - 1) x 100."
    print unstable?"\nStabilite : series instables ; ecarts descriptifs a confirmer.":"\nStabilite : series stables."
    print "\nFPS DE CHAQUE PASSAGE"
    print "N = Silex/Natif ; L = Silex/LLVM ; C = C++/Clang."
    printf "\n%-12s %5s %-9s %14s %14s %14s\n","Phase","Tour","Ordre","Silex/Natif","Silex/LLVM","C++/Clang"
    print "----------------------------------------------------------------------------"
    for(i=1;i<=last;i++)printf "%-12s %5d %-9s %14s %14s %14s\n",phase[i],i,order[i],value[i,0],value[i,1],value[i,2]
    exit unstable?2:0
}
AWK_REPORT
round=1
while [ "$round" -le $((warmups + runs)) ]; do
    phase=Mesure
    [ "$round" -gt "$warmups" ] || phase=Echauffement
    case $(((round-1)%6)) in
        0) order='0 1 2' ;; 1) order='0 2 1' ;; 2) order='1 0 2' ;;
        3) order='1 2 0' ;; 4) order='2 0 1' ;; 5) order='2 1 0' ;;
    esac
    position=0
    for index_id in $order; do
        position=$((position+1))
        case $index_id in
            0) label=Silex/Natif; prefix=SILEX_GFX_BOIDS ;;
            1) label=Silex/LLVM; prefix=SILEX_GFX_BOIDS ;;
            2) label=C++/Clang; prefix=CPP_ARCHITECTURAL_BOIDS ;;
        esac
        executable=$(executable_for "$index_id")
        printf '%-12s %2s/%s  %-12s ' "$phase" "$round" "$((warmups+runs))" "$label"
        code=0
        (cd -- "$root" && exec "$executable" 4000 480) > "$scratch/stdout" 2> "$scratch/stderr" || code=$?
        if [ "$code" -ne 0 ] || [ -s "$scratch/stderr" ]; then
            { printf '%s : code %s\n' "$label" "$code"; cat "$scratch/stderr"; } > "$scratch/failure"
            fail "Echec de $label : code $code ou stderr non vide."
        fi
        if ! fps=$(awk -v prefix="$prefix" -v index_id="$index_id" -v reference="$scratch/reference" -f "$scratch/validate.awk" "$scratch/reference" "$scratch/stdout" 2> "$scratch/failure"); then
            cat "$scratch/failure" >&2
            fail "Temoin invalide : $label"
        fi
        printf '%s\t%s\t%s\t%s\t%s\n' "$phase" "$round" "$position" "$index_id" "$fps" >> "$scratch/samples"
        printf '%s FPS\n' "$fps"
    done
    round=$((round+1))
done
verify
cat "$scratch/header" > "$scratch/report"
verdict=0
awk -v runs="$runs" -f "$scratch/report.awk" "$scratch/samples" >> "$scratch/report" || verdict=$?
[ "$verdict" -eq 0 ] || [ "$verdict" -eq 2 ] || fail 'Impossible de calculer le rapport.'
printf '\nEntrees SHA-256 : %s\n' "$config_hash" >> "$scratch/report"
cat "$scratch/report" > "$output"
finished=yes
cat "$output"
printf '\nRapport : %s\n' "$output"
exit "$verdict"
