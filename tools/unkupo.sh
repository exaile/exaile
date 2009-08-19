

MERGES=`find $1 -name "*.po"`

for m in $MERGES; do
    lc=`echo $m | cut -d - -f 2 | cut -c 1-2`
    mkdir -p po/$lc/LC_MESSAGES/
    cp $m po/$lc/LC_MESSAGES/exaile.po
done
