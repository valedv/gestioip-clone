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

my $base_uri = $gip->get_base_uri();

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("","$lang");
my $server_proto=$gip->get_server_proto();

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $client_name = $gip->get_client_from_id("$client_id");

my $ip_version_ele=$gip->get_ip_version_ele() || "v4";

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$client_name - $$lang_vars{statistics_message}","$vars_file");


my $anz_red_all=$gip->count_red_entries_all("$client_id","NULL","NULL");
my $anz_host_all=$gip->count_all_host_entries("$client_id");

my @stat_net_cats = $gip->get_stat_net_cats("$client_id");
my @stat_net_locs = $gip->get_stat_net_locs("$client_id");

#print "<p>$$lang_vars{statistics_message}<p><br>\n";
print "<p>\n";
print "<table border=\"0\">\n";
print "<tr class=\"stat_table\"><td>";
print "<b>$$lang_vars{networks_total_message}</b></td><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>$$lang_vars{hosts_total_message}</td>\n";
print "</tr><tr class=\"stat_table\" align=\"center\">";
print "<td><b>$anz_red_all</b></td><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<b>$anz_host_all</b></b>\n";
print "</td></tr>\n";
print "</table>\n";

my $i=0;;
my %counts = ();
for (@stat_net_cats) {
	$counts{$stat_net_cats[$i++]->[0]}++;
}
foreach my $keys (sort keys %counts) {
}
print "<p><br>";

print "<b>$$lang_vars{networks_by_categories_and_sites_message}</b><p>\n";
print "<table border=\"0\" valign=\"top\" cellspacing=\"0\"><tr class=\"stat_table\"><td valign=\"top\" align=\"left\">\n";

print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td><b>$$lang_vars{cat_message}</b></td><td><b>$$lang_vars{redes_dispo_message} ($$lang_vars{hosts1_message})</b></td></tr>\n";
my $count_null;
foreach my $keys (sort keys %counts) {
	my @stat_host_num_cat = $gip->get_stat_host_num_cat("$client_id","$keys");
	my $count_tot = "0";
	my $k = "0";
	foreach ( @stat_host_num_cat) {
		my $count = $gip->count_stat_host_num("$client_id","$stat_host_num_cat[$k++]->[0]") || "0";
		$count_tot = $count_tot + $count;
	}
	if ( $keys eq "NULL" ) {
		$count_null=$count_tot;
	} else {
		print "<tr><td>$keys</td><td>$counts{$keys} ($count_tot)</td></tr>";
	}
}
print "<tr><td>$$lang_vars{without_cat_message}</td><td>$counts{'NULL'} ($count_null)</td></tr>" if $counts{'NULL'};
print "</table>\n";

print "</td><td>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</td><td valign=\"top\" align=\"left\">\n";

$i=0;
%counts = ();
for (@stat_net_locs) {
	$counts{$stat_net_locs[$i++]->[0]}++;
}
print "<table border=\"0\" cellspacing=\"10\">\n";

print "<tr><td><b>$$lang_vars{loc_message}</b></td><td><b>$$lang_vars{redes_dispo_message} ($$lang_vars{hosts1_message})</b></td></tr>\n";
foreach my $keys (sort keys %counts) {
	my @stat_host_num_loc = $gip->get_stat_host_num_loc("$client_id","$keys");
	my $count_tot = "0";
	my $k = "0";
	foreach ( @stat_host_num_loc) {
		my $count = $gip->count_stat_host_num("$client_id","$stat_host_num_loc[$k++]->[0]");
		$count_tot = $count_tot + $count;
	}
	if ( $keys eq "NULL" ) {
		$count_null=$count_tot;
	} else {
		print "<tr><td>$keys</td><td>$counts{$keys} ($count_tot)</td></tr>";
	}
}
print "<tr><td>$$lang_vars{without_loc_message}</td><td>$counts{'NULL'} ($count_null)</td></tr>" if $counts{'NULL'};

print "</table>\n";

print "</td></tr>\n";
print "</table>\n";

print "<p><br>\n";
print "<p><b>$$lang_vars{network_occu_message}</b><p>\n";

print "<form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_percent_usage.cgi\">\n";
print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td align=\"right\">$$lang_vars{percent_network_usage_bigger_than_message} <select name=\"percent_usage\" size=\"1\">\n";
my @values_percent_usage = ("1","5","10","20","30","40","50","60","70","80","90","95","98");
foreach (@values_percent_usage) {
	if ( $_ eq 90 ) {
		print "<option selected>$_</option>";
		next;
	}
	print "<option>$_</option>";
}
print "</select>%\n";
print "&nbsp;&nbsp;&nbsp; $$lang_vars{filter_message} <input type=\"text\" size=\"15\" name=\"filter\" value=\"\" maxlength=\"45\">\n";
print "&nbsp;&nbsp;&nbsp;<input type=\"hidden\" name=\"stat_type\" value=\"percent_network_bigger\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"hidden\" name=\"ip_version_ele\" value=\"$ip_version_ele\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></td></tr>\n";
print "</table></form>\n";

print "<p>\n";
print "<form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_percent_usage.cgi\">\n";
print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td align=\"right\">$$lang_vars{percent_network_usage_smaller_than_message} <select name=\"percent_usage\" size=\"1\">\n";
@values_percent_usage = ("1","3","5","10","20","30","40","50","60","70","80","90","95","98");
foreach (@values_percent_usage) {
	if ( $_ eq 10 ) {
		print "<option selected>$_</option>";
		next;
	}
	print "<option>$_</option>";
}
print "</select>%\n";
print "&nbsp;&nbsp;&nbsp; $$lang_vars{filter_message} <input type=\"text\" size=\"15\" name=\"filter\" value=\"\" maxlength=\"45\">\n";
print "&nbsp;&nbsp;&nbsp;<input type=\"hidden\" name=\"stat_type\" value=\"percent_network_smaller\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"hidden\" name=\"ip_version_ele\" value=\"$ip_version_ele\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></td></tr>\n";
print "</table></form>\n";


print "<br><p><b>$$lang_vars{range_occu_message}</b><p>\n";
print "<form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_percent_usage.cgi\">\n";
print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td align=\"right\">$$lang_vars{percent_range_usage_bigger_than_message} <select name=\"percent_usage\" size=\"1\">\n";
@values_percent_usage = ("1","5","10","20","30","40","50","60","70","80","90","95","98");
foreach (@values_percent_usage) {
	if ( $_ eq 90 ) {
		print "<option selected>$_</option>";
		next;
	}
	print "<option>$_</option>";
}
print "</select>%\n";
#print "&nbsp;&nbsp;&nbsp; $$lang_vars{filter_message} <input type=\"text\" size=\"15\" name=\"filter\" value=\"\" maxlength=\"45\">\n";
print "&nbsp;&nbsp;&nbsp;<input type=\"hidden\" name=\"stat_type\" value=\"percent_range_bigger\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></td></tr>\n";
print "</table></form>\n";

print "<p>\n";
print "<form method=\"POST\" action=\"$server_proto://$base_uri/ip_show_percent_usage.cgi\">\n";
print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td align=\"right\">$$lang_vars{percent_range_usage_smaller_than_message} <select name=\"percent_usage\" size=\"1\">\n";
@values_percent_usage = ("1","3","5","10","20","30","40","50","60","70","80","90","95","98");
foreach (@values_percent_usage) {
	if ( $_ eq 10 ) {
		print "<option selected>$_</option>";
		next;
	}
	print "<option>$_</option>";
}
print "</select>%\n";
print "&nbsp;&nbsp;&nbsp;<input type=\"hidden\" name=\"stat_type\" value=\"percent_range_smaller\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></td></tr>\n";
print "</table></form>\n";


print "<br><p><b>$$lang_vars{misc_message}</b><p>\n";
print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td>$$lang_vars{down_hosts_networks_message}: </td>";
print "<td><form  method=\"POST\" action=\"$server_proto://$base_uri/ip_show_networks_host_down.cgi\"><input type=\"hidden\" name=\"down_hosts\" value=\"down\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></form></td></tr></table>\n";

print "<table border=\"0\" cellspacing=\"10\">\n";
print "<tr><td>$$lang_vars{down_never_checked_hosts_networks_message}: </td>";
print "<td><form  method=\"POST\" action=\"$server_proto://$base_uri/ip_show_networks_host_down.cgi\"><input type=\"hidden\" name=\"down_hosts\" value=\"down_and_never_checked\"><input type=\"hidden\" name=\"client_id\" value=\"$client_id\"><input type=\"submit\" class=\"input_link_w\" value=\"$$lang_vars{show_message}\" name=\"B1\"></form></td></tr></table>\n";


$gip->print_end("$client_id");
