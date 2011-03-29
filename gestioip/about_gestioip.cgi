#!/usr/bin/perl -T -w


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
use DBI;
use lib './modules';
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten") if $daten;

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{about_message}","$vars_file");

my $version=$gip->get_version();
my $anz_clients_all=$gip->count_clients("$client_id");
my $anz_red_all=$gip->count_red_entries_all("$client_id","NULL","NULL","all");
my $anz_host_all=$gip->count_all_host_entries("$client_id","all");
print "<p>";
print "<span class=\"AboutTextGestio\">$$lang_vars{gestioip_message}</span> <span class=\"AboutTextGestioVersion\">$$lang_vars{version_message}$version</span><p>\n";
print "<span class=\"AboutTextGestioIPAM\">$$lang_vars{ip_address_management_message}</span><p>\n";
print "<p><br>$$lang_vars{copyright_message}";
print "<p><br><p>";
print "<table width=\"30%\"><tr><td>\n";
print "$$lang_vars{redes_total_messages}</td></tr>\n";
if ( $anz_clients_all > 1 ) {
	print "<tr><td><span class=\"table_text_about\"><b>$anz_clients_all</b> $$lang_vars{clients_message}</span></td></tr>\n";
	print "<tr><td></b>$$lang_vars{con_message}</td></tr><tr>\n";
	if ( $anz_red_all == 1 ) {
		print "<tr><td><span class=\"table_text_about\"><b>$anz_red_all</b> $$lang_vars{network_message}</span></td></tr>\n";
	} else {
		print "<tr><td><span class=\"table_text_about\"><b>$anz_red_all</b> $$lang_vars{about_redes_dispo_message}</span></td></tr>\n";
	}
	print "<tr><td></b>$$lang_vars{y_message}</td></tr><tr>\n";
} else {
	if ( $anz_red_all == 1 ) {
		print "<tr><td><span class=\"table_text_about\"><b>$anz_red_all</b> $$lang_vars{network_message}</span></td></tr>\n";
	} else {
		print "<tr><td><span class=\"table_text_about\"><b>$anz_red_all</b> $$lang_vars{about_redes_dispo_message}</span></td></tr>\n";
	}
	print "<tr><td></b>$$lang_vars{con_message}</td></tr><tr>\n";
}
print "<td><span class=\"table_text_about\"><b>$anz_host_all</b> $$lang_vars{entradas_host_message}</span></td></tr>";
print "</table>\n";
print "<br><p><br>";
print "<p><br><p>";
print "$$lang_vars{visita_gestioip_message}\n";
print "<br><p><br>";
print "<p><br><p>";

$gip->print_end("$client_id","$vars_file");
