#!/usr/bin/perl -w

# Copyright (C) 2011 Marc Uebel

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


use strict;
use lib '../modules';
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $base_uri = $gip->get_base_uri();
my $server_proto=$gip->get_server_proto();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");


my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{initialize_gestioip_message}","$vars_file");


my $kill_prog="/usr/share/gestioip/bin/web/web_kill_procs.pl";
$gip->print_error("$client_id","$$lang_vars{kill_prog_not_found}") if ! -x $kill_prog;


my $pid;
if ($pid = fork) {

	print "<p>\n";
	print "<b>$$lang_vars{stopping_discovery_message}</b>";
	print "<p><br>\n";
	print "<FORM ACTION=\"\" style=\"display:inline;\"><INPUT TYPE=\"BUTTON\" VALUE=\"$$lang_vars{consult_discovery_status_message}\" ONCLICK=\"window.open('$server_proto://$base_uri/status/ini_stat.html','STATUS','toolbar=0,scrollbars=1,location=1,status=1,menubar=0,directories=0,right=100,top=100,width=475,height=475,resizable')\" class=\"input_link_w\"></FORM>\n";

	$gip->print_end("$client_id");


} else {

	close (STDERR);
	close (STDOUT);
	close (STDIN);

	my $user=$ENV{'REMOTE_USER'};
	exec ("$kill_prog -i $client_id -u $user");

	exit 0;
}
