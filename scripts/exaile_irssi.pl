#!/usr/bin/perl

use Net::DBus;
use strict;
use Irssi;
use vars qw($VERSION %IRSSI);

my $star_full = '✮';
my $star_empty = '✩';

$VERSION = "1.0";
%IRSSI = (
	authors => "Adam Olsen",
	contact => "arolsen\@gmail.com",
	name => "Exaile interface script",
	description => "Prints what you're playing to an irssi channel",
	license => "Public domain"
);

sub test_dbus
{
	my $service = shift;

	my $bus = Net::DBus->session;
	my $obj = $bus->get_service("org.freedesktop.DBus");
	my $iface = $obj->get_object("/org/freedesktop/DBus", 
		"org.freedesktop.DBus");

	foreach my $item( @{$iface->ListNames()} )
	{
		if( $item eq $service )
		{
			return 1;
		}
	}

	return 0;
}

sub print_info
{
	my($data, $server, $witem) = @_;

	my $bus = Net::DBus->session;

	if(!&test_dbus("org.exaile.DBusInterface"))
	{
		print "Could not see Exaile in dbus.";
		return;
	}

	my $obj = $bus->get_service("org.exaile.DBusInterface");
	my $iface = $obj->get_object("/DBusInterfaceObject",
		"org.exaile.DBusInterface");

	my $pos = $iface->current_position;
	if(!$pos)
	{	
		print "Not playing anything";
		return;
	}
	$pos = int($pos);

	my $song = $iface->get_title;
	my $artist = $iface->get_artist;
	my $length = $iface->get_length;
	my $rating = $iface->get_rating;
	my $star_string = '';
	my $count = 0;

	if($rating)
	{
		while($count < 5)
		{
			if($rating > $count)
			{
				$star_string .= $star_full;
			}
			else {
				$star_string .= $star_empty;
			}
			$count++;
		}

		$star_string = " ($star_string)";
	}

	if($witem && $witem->{type} eq 'CHANNEL')
	{
		$witem->command("ACTION " . $witem->{name} .
			" is playing $song by $artist [$length $pos\%]$star_string");
	}
}

Irssi::command_bind("exaile", 'print_info');
print "Exaile script loaded.";
