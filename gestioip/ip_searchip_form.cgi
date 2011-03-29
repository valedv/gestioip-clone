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
my %daten=$gip->preparer($daten);

my $base_uri=$gip->get_base_uri();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file)=$gip->get_lang("","$lang");
my $server_proto=$gip->get_server_proto();

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();

my @values_locations=$gip->get_loc("$client_id");
my @values_categorias=$gip->get_cat("$client_id");
my $anz_clients_all=$gip->count_clients("$client_id");

$gip->print_init("$$lang_vars{buscar_host_message}","$$lang_vars{busqueda_detallada_message} $$lang_vars{hosts_message}","$$lang_vars{busqueda_detallada_message} $$lang_vars{hosts_message}","$vars_file","$client_id");

print "<br><form method=\"POST\" name=\"searchip\" action=\"$server_proto://$base_uri/ip_searchip.cgi\">\n";
print "<table border=\"0\" cellpadding=\"5\" cellspacing=\"2\"><tr><td>";

if ( $anz_clients_all > 1 ) {
        print "$$lang_vars{client_independent_message}</td><td><input type=\"checkbox\" name=\"client_independent\" value=\"yes\">";
        print "</td></tr><tr><td>";
}

print "$$lang_vars{hostname_message}:</td><td><input name=\"hostname\" type=\"text\"  size=\"10\" maxlength=\"30\">";
print " exact match: <input type=\"checkbox\" name=\"hostname_exact\" value=\"on\"></td></tr><tr><td>"; 
print "$$lang_vars{description_message}:</td><td><input name=\"host_descr\" type=\"text\"  size=\"15\" maxlength=\"30\"></td><td>";
print "</td></tr><tr><td>";
print "$$lang_vars{comentario_message}:</td><td><input name=\"comentario\" type=\"text\"  size=\"15\" maxlength=\"30\"><br>";
print "</td></tr><tr><td>";
print "IP:</td><td><input name=\"ip\" type=\"text\"  size=\"15\" maxlength=\"15\"><br>";
print "</td></tr><tr><td>";
print "$$lang_vars{loc_message}:</td><td><select name=\"loc\" size=\"1\">";
print "<option></option>";
my $j=0;
foreach (@values_locations) {
        $values_locations[$j]->[0] = "" if ( $values_locations[$j]->[0] eq "NULL" );
        print "<option>$values_locations[$j]->[0]</option>" if ( $values_locations[$j]->[0] );
        $j++;
}

print "</select>";
print "</td></tr><tr><td>";
print "$$lang_vars{cat_message}:</td><td> <select name=\"cat\" size=\"1\">";
print "<option></option>";
$j=0;
foreach (@values_categorias) {
        $values_categorias[$j]->[0] = "" if ( $values_categorias[$j]->[0] eq "NULL" );
        print "<option>$values_categorias[$j]->[0]</option>" if ( $values_categorias[$j]->[0] );
        $j++;
}
print "</select>";
print "</td></tr><tr><td colspan=\"2\">";
print "<input type=\"checkbox\" name=\"int_admin\" value=\"y\"> $$lang_vars{ia_message}<br>\n";
print "</td></tr></table>";

print "<br><p><input name=\"client_id\" type=\"hidden\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{buscar_message}\" name=\"B2\" class=\"input_link_w\"></form>\n";

print "<script type=\"text/javascript\">\n";
print "document.searchip.hostname.focus();\n";
print "</script>\n";

$gip->print_end("$client_id");
