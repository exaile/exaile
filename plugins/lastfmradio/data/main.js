var noupdate = 0;
var streaming = -1;
var trackprogress = 0;
var trackduration = 0;
var refreshtimer = 0;

function set(id, cont) {
    e = document.getElementById(id);
    if(!e) { if(id != 'debug') set('debug', 'err:' + id); return; }
    e.innerHTML = cont;
}

function refresh() {
    r('/np');
}

function skip() {
    set('lfmp-dyn-station', 'Skipping...');
    r('/skip?r=' + Math.random());
}

function love() {
    set('lfmp-dyn-station', 'Loving...');
    r('/love');
}

function ban() {
    set('lfmp-dyn-station', 'Banning...');
    r('/ban');
}

function selectstation() {
    if(noupdate) return;
    set('lfmp-dyn-station', 'Changing station...');
    r('/changestation/' + document.lfmpform.stationselect.options[document.lfmpform.stationselect.selectedIndex].value);
}

function togglertp() {
    if(noupdate) return;
    set('lfmp-dyn-station', 'Toggling Record to profile...');
    r('/' + (document.lfmpform.rtp.checked ? 'rtp' : 'nortp'));
}

function pad(x) { if(x < 10) return '0' + x; return x; }
function fmt(x) { return pad(Math.floor(x/60)) + ':' + pad(x%60); }

function tick() { 
    setTimeout('tick();', 1000); 
    if(trackprogress || trackduration) {
        set('lfmp-dyn-dur', fmt(trackprogress) + ' / ' + fmt(trackduration));
        if(!trackduration || (trackprogress < trackduration)) trackprogress++;
    }
    if(refreshtimer-- < 0) {
        refreshtimer = 60;
        refresh();
    }
}

function processresponse(res) {
    np_metadata_age = -1;
    np_streaming = 0;
    np_lasttracks = np_bookmarks = 0;
    result = '';
    np_albumcover_medium = 'data/noalbum_medium.gif';

    eval(res);

    set('debug', res);

    if(np_lasttracks) {
        tmp = '<ul>';
        for(i = 1; i < np_lasttracks; i++) {
            tmp = tmp + '<li>' + np_lasttrack[i] + '\n';
        }
        tmp = tmp + '</ul>\n';
        set('lfmp-dyn-lasttracks-list', tmp);
    }
    if(np_bookmarks) {
        noupdate = 1;
        document.lfmpform.stationselect.options.length = 0;
        for(i = 0; i < np_bookmarks; i++) {
            tmp = decodeURI(np_bookmark[i]);
            tmp = tmp.substring(9);
            if(tmp.substring(0,11) == 'globaltags/')
                tmp = tmp.substring(11);
            if(tmp.substring(0,5) == 'user/')
                tmp = tmp.substring(5);
            if(tmp.length > 30)
                tmp = tmp.substring(0,27) + '...';
            document.lfmpform.stationselect.options[i] = new Option(tmp, np_bookmark[i]);
        }
        noupdate = 0;
    }
    
    if(result) {
        set('lfmp-dyn-station', result);
        refreshtimer = 5;
    }
    else if(np_streaming == 0) {
        set('lfmp-dyn-artist', '&nbsp;');
        set('lfmp-dyn-album', '&nbsp;');
        set('lfmp-dyn-track', '&nbsp;');
        set('lfmp-dyn-cover', '<img width=130 height=130 src="/data/noalbum_medium.gif">');
        set('lfmp-dyn-dur', '&nbsp;');
        set('lfmp-dyn-station', 'Start radio');

        trackprogress = trackduration = 0;
        refreshtimer = 5;

        if(streaming != 0) {
            document.getElementById('lfmp-buttons1').style.display = 'none';
            document.getElementById('lfmp-buttons2').style.display = 'inline';
            streaming = 0;
        }
    }
    else if(np_streaming == 1) {
        set('lfmp-dyn-artist', '<a target="_blank" href="' + np_artistpage + '">' + np_creator + '</a>');
        set('lfmp-dyn-album', '<a target="_blank" href="' + "" + '">' + np_album + '</a>');
        set('lfmp-dyn-track', '<a target="_blank" href="' + np_trackpage + '">' + np_title + '</a>');
        if(!np_image)
            np_image = "data/noalbum_medium.gif";
        set('lfmp-dyn-cover', '<img width=130 height=130 src="' + np_image + '">');
        set('lfmp-dyn-similarlink', '[<a href="javascript:r(\'/changestation/lastfm://artist/'+encodeURI(np_creator)+'/similarartists\')">sim</a>]');
        set('lfmp-dyn-fanslink', '[<a href="javascript:r(\'/changestation/lastfm://artist/'+encodeURI(np_creator)+'/fans\')">fans</a>]');
        trackprogress = np_metadata_age + parseInt(np_trackprogress);
        trackduration = parseInt(np_duration) / 1000;

        if(trackduration > 0) {
            if(trackprogress > trackduration) trackprogress = trackduration;
            refreshtimer = trackduration - trackprogress;
        }
        if(refreshtimer < 2)
            refreshtimer = 2;
        else if(refreshtimer > 15)
            refreshtimer = 15;

        set('lfmp-dyn-station', decodeURI(np_station.replace(/\+/g, " ")));

        document.title = np_creator + " - " + np_title + " - LastFMProxy";

        noupdate = 1;
        document.lfmpform.rtp.checked = np_recordtoprofile == '1' ? 1 : 0;
        noupdate = 0;

        if(streaming != 1) {
            document.getElementById('lfmp-buttons1').style.display = 'inline';
            document.getElementById('lfmp-buttons2').style.display = 'none';
            streaming = 1;
        }
    }
}

function r(url) {
    set('debug',url);
    url = host + url;
    if (window.ActiveXObject) {
        objHTTPchat = new ActiveXObject("Microsoft.XMLHTTP");
        objHTTPchat.Open('GET',url,false);
        objHTTPchat.Send();

        response=objHTTPchat.responseText;
        objHTTPchat=null;
        processresponse(response);
    }
    else if (window.XMLHttpRequest) {
        objHTTPchat = new XMLHttpRequest();
        objHTTPchat.open('GET',url,true);
        objHTTPchat.onreadystatechange = function() {
            if(objHTTPchat.readyState == 4) {
                response=objHTTPchat.responseText;
                objHTTPchat=null;
                processresponse(response);
            }
        }
        objHTTPchat.send(null);
    }
}

document.onkeydown = function(key) {
	switch (key.which) {
		case 8: // backspace
			ban();
			break;
		case 13: // enter
			love();
			break;
		case 32: // space
			skip();
			break;
		case 69: // e
			document.lfmpform.rtp.click();
			break;
		case 82: // r
			refresh();
			break;
	}
}
