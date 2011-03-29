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
use lib '../modules';
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten) if $daten;

my $base_uri = $gip->get_base_uri();
my ($lang_vars,$vars_file)=$gip->get_lang();
my $server_proto=$gip->get_server_proto();

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
if ( $client_id !~ /^\d{1,4}$/ ) {
        $client_id = 1;
        $gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{redes_message}","$vars_file");
        $gip->print_error("$client_id","$$lang_vars{formato_malo_message}");
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{export_message}","$vars_file");

my @global_config = $gip->get_global_config("$client_id");
my $ipv4_only_mode=$global_config[0]->[5] || "yes";

my $start_entry=$daten{'start_entry'} || '0';
$gip->print_error("$client_id",$$lang_vars{formato_malo_message}) if $start_entry !~ /^\d{1,4}$/;

print "<p><b>$$lang_vars{export_network_list_message}</b><p>\n";
print "<form name=\"export_redlist_form\" method=\"POST\" action=\"$server_proto://$base_uri/res/ip_export.cgi\">\n";
print "<table border=\"0\"><tr>\n";
print "<td align=\"right\">$$lang_vars{all_networks_message}</td><td><input type=\"radio\" name=\"export_radio\" value=\"all\"  onclick=\"export_match.disabled=true;export_match.value = '';\" checked></td></tr>\n";

if ( $ipv4_only_mode ne "yes" ) {
print <<EOF;
<tr><td align="right"> $$lang_vars{ip_version_message}</td>
        <td colspan="3">&nbsp;&nbsp;&nbsp;v4<input type="checkbox" name="ipv4" value="ipv4" checked>&nbsp;&nbsp;&nbsp;v6<input type="checkbox" name="ipv6" value="ipv6"></td></tr>
EOF
} else {
print <<EOF;
	<tr><td><input type="hidden" name="ipv4" value="ipv4"></td></tr>
EOF
}

print "<td align=\"right\">$$lang_vars{export_net_match_message}</td><td><input type=\"radio\" name=\"export_radio\" value=\"match\"  onclick=\"export_match.disabled=false;\">\n";
print "<input name=\"export_match\" type=\"text\"  size=\"20\" maxlength=\"150\" disabled></td></tr>\n";
print "<tr><td><p><br><input name=\"export_type\" type=\"hidden\" value=\"net\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{export_message}\" name=\"B2\" class=\"input_link_w\"></form></td><td></td></tr></table>\n";

## HOSTS
print "<p><br><p><b>$$lang_vars{export_host_list_message}</b><p>\n";
print "<form name=\"export_hostlist_form\" method=\"POST\" action=\"$server_proto://$base_uri/res/ip_export.cgi\">\n";
print "<table border=\"0\"><tr>\n";
print "<td align=\"right\">$$lang_vars{all_hosts_message}</td><td><input type=\"radio\" name=\"export_radio\" value=\"all\" onclick=\"network_match.disabled=true;network_match.value = '';export_match.disabled=true;export_match.value = '';\" checked></td></tr>\n";

if ( $ipv4_only_mode ne "yes" ) {
print <<EOF;
<tr><td align="right"> $$lang_vars{ip_version_message}</td>
        <td colspan="3">&nbsp;&nbsp;&nbsp;v4<input type="checkbox" name="ipv4" value="ipv4" checked>&nbsp;&nbsp;&nbsp;v6<input type="checkbox" name="ipv6" value="ipv6"></td></tr>
EOF
}

print "<td align=\"right\">$$lang_vars{export_host_network_message}</td><td><input type=\"radio\" name=\"export_radio\" value=\"network\" onclick=\"network_match.disabled=false;export_match.disabled=true;export_match.value = '';\">\n";
print "<input name=\"network_match\" type=\"text\"  size=\"20\" maxlength=\"150\" disabled> $$lang_vars{example_network_message}</td></tr>\n";
print "<td align=\"right\">$$lang_vars{export_host_match_message}</td><td><input type=\"radio\" name=\"export_radio\" value=\"match\" onclick=\"network_match.disabled=true;network_match.value = '';export_match.disabled=false;\">\n";
print "<input name=\"export_match\" type=\"text\"  size=\"20\" maxlength=\"150\" disabled></td></tr>\n";
print "<tr><td><p><br><input name=\"export_type\" type=\"hidden\" value=\"host\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" value=\"$$lang_vars{export_message}\" name=\"B2\" class=\"input_link_w\"></form></td><td></td></tr></table>\n";

print "<script type=\"text/javascript\">\n";
print "document.export_redlist_form.export_red_match.focus();\n";
print "</script>\n";

$gip->print_end("$client_id");
