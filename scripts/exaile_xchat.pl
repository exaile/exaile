#!/usr/bin/perl
#Author sartek
 
use Net::DBus;
 
Xchat::register("Exaile! XChat announcer", "1.0", "Prints what you're playing", \&unload);
Xchat::print("Exaile! XChat script loaded");
Xchat::hook_command("exaile", \&print_info);
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
	Xchat::command ("me is playing $song by $artist [$length $pos\%]");
 
}
sub unload {
    Xchat::print("Exaile! XChat unloaded");
}
