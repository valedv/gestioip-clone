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
my ($lang_vars,$vars_file,$entries_per_page);
if ( $daten{'entries_per_page'} ) {
	$daten{'entries_per_page'} = "500" if $daten{'entries_per_page'} !~ /^\d{1,3}$/; 
	($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("$daten{'entries_per_page'}","$lang");
} else {
	($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("","$lang");
}

my $first_client_id = $gip->get_first_client_id();
my $client_id = $daten{'client_id'} || $gip->get_default_client_id("$first_client_id");

my @global_config = $gip->get_global_config("$client_id");
my $ipv4_only_mode=$global_config[0]->[5] || "yes";
my $ip_version_ele="";
if ( $ipv4_only_mode eq "no" ) {
	$ip_version_ele = $daten{'ip_version_ele'} || "";
	if ( $ip_version_ele ) {
		$ip_version_ele = $gip->set_ip_version_ele("$ip_version_ele");
	} else {
		$ip_version_ele = $gip->get_ip_version_ele();
	}
} else {
	$ip_version_ele = "v4";
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{redes_dispo_message}","$vars_file");

my $tipo_ele = $daten{'tipo_ele'} || "NULL";
my $loc_ele = $daten{'loc_ele'} || "NULL";
my $start_entry=$daten{'start_entry'} || '0';
my $order_by=$daten{'order_by'} || 'red_auf';
$gip->print_error("$client_id",$$lang_vars{formato_malo_message}) if $start_entry !~ /^\d{1,4}$/;

my $tipo_ele_id=$gip->get_cat_net_id("$client_id","$tipo_ele") || "-1";
my $loc_ele_id=$gip->get_loc_id("$client_id","$loc_ele") || "-1";
my $anz_values_redes = $gip->count_red_entries_all("$client_id","$tipo_ele","$loc_ele");
my $pages_links=$gip->get_pages_links_red("$client_id","$start_entry","$anz_values_redes","$entries_per_page","$tipo_ele","$loc_ele","$order_by");
my @ip=$gip->get_redes("$client_id","$tipo_ele_id","$loc_ele_id","$start_entry","$entries_per_page","$order_by","$ip_version_ele");
my $ip=$gip->prepare_redes_array("$client_id",\@ip,"$order_by","$start_entry","$entries_per_page","$ip_version_ele");


if ( $ip[0] ) {
	$gip->PrintRedTabHead("$client_id","$vars_file","$start_entry","$entries_per_page","$pages_links","$tipo_ele","$loc_ele","$ip_version_ele");
	$gip->PrintRedTab("$client_id",$ip,"$vars_file","simple","$start_entry","$tipo_ele","$loc_ele","$order_by","","$entries_per_page","$ip_version_ele");
} else {
	if ( $ip_version_ele eq "v4" ) {
		$gip->PrintRedTabHead("$client_id","$vars_file","$start_entry","$entries_per_page","$pages_links","$tipo_ele","$loc_ele","$ip_version_ele");
		print "<p class=\"NotifyText\">$$lang_vars{no_networks_message}</p><br>\n";
	} else {
		$gip->PrintRedTabHead("$client_id","$vars_file","$start_entry","$entries_per_page","$pages_links","$tipo_ele","$loc_ele","$ip_version_ele");
		print "<p class=\"NotifyText\">$$lang_vars{no_ipv6_networks_message}</p><br>\n";
	}
}

$gip->print_end("$client_id","$vars_file","go_to_top");
