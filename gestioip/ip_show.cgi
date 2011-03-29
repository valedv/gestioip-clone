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
use Net::IP;
use Net::IP qw(:PROC);
use lib './modules';
use GestioIP;
use Math::BigInt;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten") if $daten;

my ($lang_vars,$vars_file,$entries_per_page_hosts);

my $lang = $daten{'lang'} || "";
($lang_vars,$vars_file)=$gip->get_lang("","$lang");

if ( $daten{'entries_per_page_hosts'} && $daten{'entries_per_page_hosts'} =~ /^\d{1,4}$/ ) {
	$entries_per_page_hosts=$daten{'entries_per_page_hosts'};	
} else {
	$entries_per_page_hosts = "254";
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $ip_version = $daten{'ip_version'};

my $red_num = "";
$red_num=$daten{'red_num'} if $daten{'red_num'};

if ( $red_num !~ /^\d{1,5}$/ ) {
	$gip->print_init("gestioip","$$lang_vars{redes_message}","$$lang_vars{redes_message}","$vars_file","$client_id");
	$gip->print_error("$client_id","$$lang_vars{formato_red_malo_message}: $red_num - $daten{'red_num'} - $daten{'client_id'} - $daten") ;
}

#my $order_by=$daten{'order_by'} || 'IP_auf';
my $host_order_by = $daten{'host_order_by'} || "IP_auf";

my $start_entry_hosts=$daten{'start_entry_hosts'} || '0';

my @values_redes = $gip->get_red("$client_id","$red_num");

my $red = "$values_redes[0]->[0]" || "";
my $BM = "$values_redes[0]->[1]" || "";
my $descr = "$values_redes[0]->[2]" || "";
my $cat_id = "$values_redes[0]->[6]" || "";
my $cat = $gip->get_cat_net_from_id("$client_id","$cat_id");
$cat = "NULL" if ! $cat;
$cat = "$cat - " || "";
$cat = "" if ( $cat =~ /NULL\s-\s/ );
$descr = "---" if ( $descr eq "NULL" );
my $redob = "$red/$BM";

$descr =~ s/^((\xC2\xA1|\xC2\xA2|\xC2\xA3|\xC2\xA4|\xC2\xA5|\xC2\xA6|\xC2\xA7|\xC2\xA8|\xC2\xA9|\xC2\xAA|\xC2\xAB|\xC2|\xC2\xAD|\xC2\xAE|\xC2\xAF|\xC2\xB0|\xC2\xB1|\xC2\xB2|\xC2\xB3|\xC2\xB4|\xC2\xB5|\xC2\xB6|\xC2\xB7|\xC2\xB8|\xC2\xB9|\xC2\xBA|\xC2\xBB|\xC2\xBC|\xC2\xBD|\xC2\xBE|\xC2\xBF|\xC3\x80|\xC3\x81|\xC3\x82|\xC3\x83|\xC3\x84|\xC3\x85|\xC3\x86|\xC3\x87|\xC3\x88|\xC3\x89|\xC3\x8A|\xC3\x8B|\xC3\x8C|\xC3\x8D|\xC3\x8E|\xC3\x8F|\xC3\x90|\xC3\x91|\xC3\x92|\xC3\x93|\xC3\x94|\xC3\x95|\xC3\x96|\xC3\x97|\xC3\x98|\xC3\x99|\xC3\x9A|\xC3\x9B|\xC3\x9C|\xC3\x9D|\xC3\x9E|\xC3\x9F|\xC3\xA0|\xC3\xA1|\xC3\xA2|\xC3\xA3|\xC3\xA4|\xC3\xA5|\xC3\xA6|\xC3\xA7|\xC3\xA8|\xC3\xA9|\xC3\xAA|\xC3\xAB|\xC3\xAC|\xC3\xAD|\xC3\xAE|\xC3\xAF|\xC3\xB0|\xC3\xB1|\xC3\xB2|\xC3\xB3|\xC3\xB4|\xC3\xB5|\xC3\xB6|\xC3\xB7|\xC3\xB8|\xC3\xB9|\xC3\xBA|\xC3\xBB|\xC3\xBC|\xC3\xBD|\xC3\xBE|\xC3\xBF|\xe2\x82\xac|\xc5\x92|\xc5\x93|\xc5\xa0|\xc5\xa1|\xc5\xb8|\xc6\x92|\w|\?|_|\.|,|:|\-|\@|\(|\/|\[|\]|{|}|\||~|\+|\n|\r|\f|\t|\s){12})(.*)/$1/;
$descr = "$descr" . "..." if $2;

my ( $first_ip_int, $last_ip_int, $start_entry);
	
my $ipob = new Net::IP ($redob) || $gip->print_error("$client_id","Can't create ip object: $!\n");
my $redint=($ipob->intip());
$redint = Math::BigInt->new("$redint");
my $redbroad_int=($ipob->last_int());
$first_ip_int = $redint + 1;
my $start_ip_int=$first_ip_int;
$last_ip_int = ($ipob->last_int());
$last_ip_int = Math::BigInt->new("$last_ip_int");
$last_ip_int = $last_ip_int - 1;


my $knownhosts = $daten{'knownhosts'} || "all";

my @values_categorias=$gip->get_cat("$client_id");

my $red_loc = $gip->get_loc_from_redid("$client_id","$red_num");
my ( $mask_bin,$mask );
if ( $ip_version eq "v4" ) {
	$mask_bin = ip_get_mask ($BM,4);
	$mask = ip_bintoip ($mask_bin,4);
} else {
	$mask_bin = ip_get_mask ($BM,6);
	$mask = ip_bintoip ($mask_bin,6);
}

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$red/$BM - $cat $descr","$vars_file");


my ($host_hash_ref,$host_sort_helper_array_ref);
($host_hash_ref,$host_sort_helper_array_ref)=$gip->get_host_hash("$client_id","$first_ip_int","$last_ip_int","$host_order_by","$knownhosts");

my $anz_host_total=$gip->get_host_hash_count("$client_id","$first_ip_int","$last_ip_int","$host_order_by","$red_num","$knownhosts") || "0";


if ( $anz_host_total >= $entries_per_page_hosts ) {
	my $last_ip_int_new = $first_ip_int + $start_entry_hosts + $entries_per_page_hosts - 1;
	$last_ip_int = $last_ip_int_new if $last_ip_int_new < $last_ip_int;
} else {
	$last_ip_int = ($ipob->last_int());
	$last_ip_int = $last_ip_int - 1;
}

my %anz_hosts_bm = $gip->get_anz_hosts_bm_hash("$client_id","$ip_version");
my $anz_values_hosts_pages = $anz_hosts_bm{$BM};
my $anz_values_hosts=$daten{'anz_values_hosts'} || $anz_hosts_bm{$BM};

if ( $knownhosts eq "hosts" ) {
	if ( $entries_per_page_hosts > $anz_values_hosts_pages ) {
		$anz_values_hosts=$anz_hosts_bm{$BM};
		$anz_values_hosts_pages=$anz_host_total;
	} else {
		$anz_values_hosts=$entries_per_page_hosts;
		$anz_values_hosts_pages=$anz_host_total;
	}
} elsif ( $knownhosts =~ /libre/ ) { 
		$anz_values_hosts_pages=$anz_hosts_bm{$BM}-$anz_host_total;
} elsif ( $host_order_by =~ /IP/ ) { 
	$anz_values_hosts=$entries_per_page_hosts;
	$anz_values_hosts_pages=$anz_hosts_bm{$BM};
} else {
	$anz_values_hosts=$anz_host_total;
	$anz_values_hosts_pages=$anz_host_total;
}

$start_entry_hosts = "0" if $start_entry_hosts >= $anz_values_hosts_pages;


($host_hash_ref,$first_ip_int,$last_ip_int)=$gip->prepare_host_hash("$client_id",$host_hash_ref,"$first_ip_int","$last_ip_int","res/ip_modip_form.cgi","$knownhosts","$$lang_vars{modificar_message}","$red_num","$red_loc","$vars_file","$anz_values_hosts","$start_entry_hosts","$entries_per_page_hosts","$host_order_by","$redbroad_int","$ip_version");

my $pages_links=$gip->get_pages_links_host("$client_id","$start_entry_hosts","$anz_values_hosts_pages","$entries_per_page_hosts","$red_num","$knownhosts","$host_order_by","$start_ip_int",$host_hash_ref,"$redbroad_int");

$gip->PrintIpTabHead("$client_id","$knownhosts","res/ip_modip_form.cgi","$red_num","$vars_file","$start_entry_hosts","$anz_values_hosts","$entries_per_page_hosts","$pages_links","$host_order_by","$ip_version");

$gip->PrintIpTab("$client_id",$host_hash_ref,"$first_ip_int","$last_ip_int","res/ip_modip_form.cgi","$knownhosts","$$lang_vars{modificar_message}","$red_num","$red_loc","$vars_file","$anz_values_hosts_pages","$start_entry_hosts","$entries_per_page_hosts","$host_order_by","$host_sort_helper_array_ref","","$ip_version");

$gip->print_end("$client_id","$vars_file","go_to_top");
