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
use lib './modules';
use DBI;
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten") if $daten;

my $base_uri=$gip->get_base_uri();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");
my $server_proto=$gip->get_server_proto();

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

my @values_locations=$gip->get_loc("$client_id");
my @values_cat_red=$gip->get_cat_net("$client_id");
my $anz_clients_all=$gip->count_clients("$client_id");

$gip->print_init("$$lang_vars{buscar_red_message}","$$lang_vars{advanced_network_search_message}","$$lang_vars{advanced_network_search_message}","$vars_file","$client_id");
print "<br><form method=\"POST\" name=\"searchread\" action=\"$server_proto://$base_uri/ip_searchred.cgi\">\n";
print "<table border=\"0\" cellpadding=\"5\" cellspacing=\"2\"><tr><td>";

if ( $anz_clients_all > 1 ) {
	print "$$lang_vars{client_independent_message}</td><td colspan=\"3\"><input type=\"checkbox\" name=\"client_independent\" value=\"yes\">";
	print "</td></tr><tr><td>";
}

print "$$lang_vars{redes_message} ID:</td><td colspan=\"3\">*<input name=\"red\" type=\"text\"  size=\"15\" maxlength=\"15\">*";
print "</td></tr><tr><td>";
print "$$lang_vars{description_message}:</td><td colspan=\"3\">*<input name=\"descr\" type=\"text\"  size=\"15\" maxlength=\"30\">*";
print "</td></tr><tr><td>";
print "$$lang_vars{comentario_message}:</td><td colspan=\"3\">*<input name=\"comentario\" type=\"text\"  size=\"15\" maxlength=\"30\">*";
print "</td></tr><tr><td>";
print "$$lang_vars{loc_message}: </td><td colspan=\"3\"><select name=\"loc\" size=\"1\">";
print "<option></option>";
my $j=0;
foreach (@values_locations) {
        print "<option>$values_locations[$j]->[0]</option>" if ( $values_locations[$j]->[0] ne "NULL" );
        $j++;
}
print "</select></td><tr><td>\n";
print "$$lang_vars{cat_message}: </td><td colspan=\"3\"><select name=\"cat_red\" size=\"1\">";
print "<option></option>";
$j=0;
foreach (@values_cat_red) {
        print "<option>$values_cat_red[$j]->[0]</option>" if ( $values_cat_red[$j]->[0] ne "NULL" );
        $j++;
}
print "</select>\n";
#print "</td></tr><tr></tr><td colspan=\"4\"><br></td><tr><td>";
print "</td></tr><tr></tr><tr><td>";
print "$$lang_vars{sincronizado_message}: </td><td><input type=\"radio\" name=\"vigilada\" value=\"\" checked> $$lang_vars{todos_message}&nbsp;&nbsp;&nbsp;&nbsp;</td><td><input type=\"radio\" name=\"vigilada\" value=\"y\"> $$lang_vars{solo_sinc_message}&nbsp;&nbsp;&nbsp;&nbsp;</td><td><input type=\"radio\" name=\"vigilada\" value=\"n\">$$lang_vars{solo_no_sinc_message}\n";
print "</td></tr></table><br>";
print "<p><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{buscar_message}\" name=\"B2\" class=\"input_link_w\"></form>&nbsp;&nbsp;&nbsp;&nbsp;";
print "<input type=\"checkbox\" name=\"modred\" value=\"y\"> <span class=\"HintText\">$$lang_vars{para_modificar_message}</span>\n";

print "<script type=\"text/javascript\">\n";
print "document.searchread.red.focus();\n";
print "</script>\n";

$gip->print_end("$client_id");

