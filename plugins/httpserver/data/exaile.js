var eh_current_filename = '### INIT VALUE ###';
var eh_current_duration = 0;
var eh_request_refresh_playlist = false;
var eh_request_refresh = false;
var eh_data_loading = '<div id="loading"><img class="loading" src="/loading.gif" alt="Loading..."/></div>';
var eh_data_playing = '<img src="/btn-play.png" alt="Playing..."/>';

var eh_tag_current = 1;
var eh_capture_seek = false;
var eh_tag = new Array();
var eh_tag_filename = new Array();
var eh_is_paused = false;
var eh_is_playing = false;
var eh_is_pause_display = false;
var eh_playlist = false;
var eh_progress = 0;

var eh_pref_default_artist = '1';
var eh_pref_default_album = '1';
var eh_pref_default_genre = '0';
var eh_pref_default_duration = '1';
var eh_pref_default_rating = '0';

function vd(el, name) {
	var e = el.getElementsByTagName(name);
	if (!e)
		return '';
	e = e[0];
	if (!e)
		return '';
	if (!e.firstChild)
		return '';
	if (e.firstChild.textContent)
		return e.firstChild.textContent;
	return e.firstChild.text;
}

function v(xh, name) {
	return vd(xh.responseXML, name);
}

function x(page, callback) {
	var xmlhttp = new Ajax.Request(page, {
		method: 'get',
		onSuccess: function(transport) {
			if (callback != false)
				callback(page, transport);
		}
	});
}

function eh_cookie_set(name, value, expires, path, domain, secure) {
	var today = new Date();
	today.setTime(today.getTime());
	if (expires)
		expires = expires * 1000 * 60 * 60 * 24;
	var expires_date = new Date( today.getTime() + (expires) );
	document.cookie = name + '=' +escape( value ) +
		(( expires ) ? ';expires=' + expires_date.toGMTString() : '' ) +
		(( path ) ? ';path=' + path : '' ) +
		(( domain ) ? ';domain=' + domain : '' ) +
		(( secure ) ? ';secure' : '' );
}

function eh_cookie_get(name, defval) {
	var start = document.cookie.indexOf(name + '=');
	var len = start + name.length + 1;
	if ((!start) && (name != document.cookie.substring(0, name.length)))
		return defval;
	if (start == -1)
		return defval;
	var end = document.cookie.indexOf(';', len);
	if (end == -1)
		end = document.cookie.length;
	return unescape(document.cookie.substring(len, end));
}

function eh_show(id) {
	$(id).style.display = 'block';
}

function eh_hide(id) {
	$(id).style.display = 'none';
}

function eh_pref(el) {
	var id = el.id;
	var val = false;
	if (el.tagName == 'SELECT') {
		val = el.value;
	} else if (el.tagName == 'INPUT') {
		if (el.type == 'checkbox')
			val = el.checked ? '1' : '0';
		else
			val = el.value;
	}
	eh_cookie_set(id, val, '', '/', '', '' );

	if (id.indexOf('eh_pref_playlist_') >= 0)
		eh_playlist_build();
}

function eh_track_current_callback(page, xh) {
	var duration;
	var duration_min;
	var text;
	eh_request_refresh = false;
	if (!xh.responseXML)
		return;
	eh_is_playing = false;
	if (v(xh, 'is_playing') == 'True')
		eh_is_playing = true;
	eh_is_paused = false;
	if (v(xh, 'is_paused') == 'True')
		eh_is_paused = true;
	if (v(xh, 'filename') != eh_current_filename) {
		eh_tag_set(eh_current_filename, '');
		eh_current_filename = v(xh, 'filename');
		eh_tag_set(eh_current_filename, eh_data_playing);
		$('trackcover').innerHTML =
			'<img src="/image/cover/current?'+eh_current_filename+'"/>';
		$('ti_artist').innerHTML = v(xh, 'artist');
		$('ti_album').innerHTML = v(xh, 'album');
		$('ti_title').innerHTML = v(xh, 'title');
		document.title = v(xh, 'title') + ' - Exaile';
	}

	$('ti_position').style.width = '' + v(xh, 'position') + '%';

	eh_current_duration = parseInt(v(xh, 'duration'));

	if (eh_is_playing && !eh_is_paused)
	{
		duration = parseInt(v(xh, 'duration')) * parseInt(v(xh, 'position')) / 100;
		duration_min = parseInt(duration % 60);
		if (duration_min < 10)
			duration_min = '0' + duration_min
		duration = parseInt(duration/60);
		text = '' + duration + ':' + duration_min + ' / ' + v(xh, 'len');
		if ($('ti_len').innerHTML != text)
			$('ti_len').innerHTML = text
	} else if (!eh_is_playing && !eh_is_paused) {
		text = '0:00 / 0:00'
		if ($('ti_len').innerHTML != text)
			$('ti_len').innerHTML = text
	}

	if (eh_is_playing)
	{
		if (!eh_is_paused) {
			if (!eh_is_pause_display) {
				eh_is_pause_display = true;
				$('action-pause').style.display = 'block';
				$('action-play').style.display = 'none';
			}
		}
		else
		{
			if (eh_is_pause_display) {
				eh_is_pause_display = false;
				$('action-pause').style.display = 'none';
				$('action-play').style.display = 'block';
			}
		}
	}
	else
	{
		if (eh_is_pause_display) {
			eh_is_pause_display = false;
			$('action-pause').style.display = 'none';
			$('action-play').style.display = 'block';
		}
	}
}

function eh_tag_set(filename, data) {
	var tag = eh_tag[filename];
	if (!tag || tag <= 0)
		return;
	var el = $('tag-' + tag);
	if (!el)
		return;
	el.innerHTML = data;
	el = $('tagth-' + tag);
	if (!el)
		return;
	if (data == '')
		el.className = '';
	else
		el.className = 'playing';
}

function eh_playlist_list_callback(page, xh) {
	eh_request_refresh_playlist = false;
	eh_playlist = xh.responseXML.getElementsByTagName('track');
	eh_playlist_build();
}

function eh_playlist_build() {
	if (eh_playlist == false)
		return;

	var rating;
	var duration;
	var duration_min;

	table = new Array();
	table.push('<table id="playlisttbl">');
	table.push('<tr><th style="width: 26px"></th>');
	table.push('<th>Title</th>');
	if (parseInt(eh_cookie_get('eh_pref_playlist_artist', eh_pref_default_artist)))
		table.push('<th style="width: 20%">Artist</th>');
	if (parseInt(eh_cookie_get('eh_pref_playlist_album', eh_pref_default_album)))
		table.push('<th style="width: 20%">Album</th>');
	if (parseInt(eh_cookie_get('eh_pref_playlist_genre', eh_pref_default_genre)))
		table.push('<th style="width: 100px">Genre</th>');
	if (parseInt(eh_cookie_get('eh_pref_playlist_duration', eh_pref_default_duration)))
		table.push('<th style="width: 30px">Duration</th>');
	if (parseInt(eh_cookie_get('eh_pref_playlist_rating', eh_pref_default_rating)))
		table.push('<th style="width: 100px">Rating</th>');
	table.push('</tr>');

	eh_tag = new Array();
	eh_tag_filename = new Array();
	for ( var i = 0; i < eh_playlist.length; i++ ) {
		var filename = vd(eh_playlist[i], 'filename');
		var tag = eh_tag_current++;
		eh_tag[filename] = tag;
		eh_tag_filename[''+tag] = filename;
		table.push('<tr id="tagth-' + tag + '" onclick="eh_playtrack('+tag+')">');
		table.push('<td id="tag-' + tag + '"></td>');
		table.push('<td><div>' + vd(eh_playlist[i], 'title') + '</div></td>');
		if (parseInt(eh_cookie_get('eh_pref_playlist_artist', eh_pref_default_artist)))
			table.push('<td><div>' + vd(eh_playlist[i], 'artist') + '</div></td>');
		if (parseInt(eh_cookie_get('eh_pref_playlist_album', eh_pref_default_album)))
			table.push('<td><div>' + vd(eh_playlist[i], 'album') + '</div></td>');
		if (parseInt(eh_cookie_get('eh_pref_playlist_genre', eh_pref_default_genre)))
			table.push('<td><div>' + vd(eh_playlist[i], 'genre') + '</div></td>');
		if (parseInt(eh_cookie_get('eh_pref_playlist_duration', eh_pref_default_duration))) {
			duration = parseInt(vd(eh_playlist[i], 'duration'));
			duration_min = duration % 60;
			if (duration_min < 10)
				duration_min = '0' + duration_min
			duration = parseInt(duration/60);
			table.push('<td><div>' + duration + ':' + duration_min + '</div></td>');
		}
		if (parseInt(eh_cookie_get('eh_pref_playlist_rating', eh_pref_default_rating))) {
			var rating = '' + vd(eh_playlist[i], 'rating');
			rating = rating.replace(' ', '', 'g');
			rating = rating.replace('*', '<img class="rating" src="/star.png"/>', 'g');
			table.push('<td><div>' + rating + '</div></td>');
		}
		table.push('<tr>');
	}

	$('playlistcontent').innerHTML = table.join('');
	eh_tag_set(eh_current_filename, eh_data_playing);
}

function eh_playtrack(t) {
	var tag = eh_tag_filename[''+t];
	if (!tag || tag == '')
		return;
	x('rpc/action/play?f='+tag, false);
}

function eh_refresh() {
	if (eh_request_refresh == true)
		return;
	eh_request_refresh = true;
	x('rpc/current', eh_track_current_callback);
	setTimeout('eh_refresh()', 1000 * parseInt(''+eh_cookie_get('eh_pref_refreshtime', 1)));
}

function eh_refresh_playlist() {
	if (eh_request_refresh_playlist == true)
		return;
	eh_request_refresh_playlist = true;
	$('playlistcontent').innerHTML = eh_data_loading;
	x('rpc/playlist/list', eh_playlist_list_callback);
}

function eh_action_previous() {
	x('rpc/action/previous', false);
}

function eh_action_play() {
	x('rpc/action/play', false);
}

function eh_action_pause() {
	x('rpc/action/pause', false);
}

function eh_action_stop() {
	x('rpc/action/stop', false);
}

function eh_action_next() {
	x('rpc/action/next', false);
}

function eh_trackbar_observe() {
	Event.observe($('trackprogressbar'), 'mouseover', function (ev) {
			if (!eh_is_playing && !eh_is_paused)
				return;
			eh_capture_seek = true;
			eh_show($('ti_positionmove'));
		});
	Event.observe($('trackprogressbar'), 'mouseout', function (ev) {
			eh_hide($('ti_positionmove'));
			eh_progress = 0;
			eh_capture_seek = false;
		});
	Event.observe($('trackprogressbar'), 'mousemove', function (ev) {
			if (!eh_capture_seek)
				return;
			var px = Event.pointerX(ev);
			var el = $('trackprogressbar');
			var elx = Position.cumulativeOffset(el)[0];
			var d = Element.getDimensions(el);
			px = px - elx;
			if (px < 0)
				return;
			px = px * 100 / d['width'];
			$('ti_positionmove').style.width = '' + px + '%';
			eh_progress = px;
		});

	Event.observe($('trackprogressbar'), 'click', function (ev) {
			if (!eh_capture_seek)
				return;
			x('rpc/action/seek?s=' + parseInt((eh_progress * eh_current_duration / 100)), false);
		});
}

function eh_init() {
	$('action-pause').style.display = 'none';

	eh_playlist = false;
	$('eh_pref_playlist_artist').checked =
		parseInt(eh_cookie_get('eh_pref_playlist_artist', eh_pref_default_artist));
	$('eh_pref_playlist_album').checked =
		parseInt(eh_cookie_get('eh_pref_playlist_album', eh_pref_default_album));
	$('eh_pref_playlist_genre').checked =
		parseInt(eh_cookie_get('eh_pref_playlist_genre', eh_pref_default_genre));
	$('eh_pref_playlist_duration').checked =
		parseInt(eh_cookie_get('eh_pref_playlist_duration', eh_pref_default_duration));
	$('eh_pref_playlist_rating').checked =
		parseInt(eh_cookie_get('eh_pref_playlist_rating', eh_pref_default_rating));

	eh_refresh();
	eh_trackbar_observe();
}
