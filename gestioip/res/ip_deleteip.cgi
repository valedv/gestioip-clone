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
use lib '../modules';
use GestioIP;
use Net::IP;
use Net::IP qw(:PROC);
use Math::BigInt;


my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer("$daten");

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page_hosts);
($lang_vars,$vars_file)=$gip->get_lang("","$lang");
if ( $daten{'entries_per_page_hosts'} && $daten{'entries_per_page_hosts'} =~ /^\d{1,4}$/ ) {
        $entries_per_page_hosts=$daten{'entries_per_page_hosts'};
} else {
        $entries_per_page_hosts = "254";
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
if ( $client_id !~ /^\d{1,4}$/ ) {
        $client_id = 1;
        $gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{borrar_host_message}","$vars_file");
        $gip->print_error("$client_id","$$lang_vars{client_id_invalid_message}");
}

if ( $daten{'ip_int'} !~ /^\d{8,40}$/ ) {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{borrar_host_message}","$vars_file");
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)");
}
if ( $daten{'red_num'} !~ /^\d{1,6}$/ ) {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{borrar_host_message}","$vars_file");
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (2)");
}

my $ip_version=$daten{'ip_version'};
	
my $ip_int=$daten{'ip_int'};
my $red_num=$daten{'red_num'};

my @values_redes = $gip->get_red("$client_id","$red_num");

my $red = "$values_redes[0]->[0]" || "";
my $BM = "$values_redes[0]->[1]" || "";
my $descr = "$values_redes[0]->[2]" || "";
my $knownhosts = $daten{'knownhosts'} || "all";
my $host_order_by = $daten{'host_order_by'} || "IP_auf";


my $ip_ad=$gip->int_to_ip("$client_id","$ip_int","$ip_version");

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{borrar_host_done_message} $ip_ad","$vars_file");

my $utype = $daten{'update_type'};
my $start_entry_hosts=$daten{'start_entry_hosts'} || '0';
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (3)") if $daten{'anz_values_hosts'} && $daten{'anz_values_hosts'} !~ /^\d{2,4}||no_value$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (4)") if $daten{'knownhosts'} && $daten{'knownhosts'} !~ /^all|hosts|libre$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (5)") if $daten{'start_entry_hosts'} && $daten{'start_entry_hosts'} !~ /^\d{1,20}$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (6)") if $ip_version !~ /^(v4|v6)$/;


my ( $first_ip_int, $last_ip_int, $start_entry);

my $redob = "$red/$BM";
my $ipob = new Net::IP ($redob) || $gip->print_error("$client_id","Can't create ip object: $!\n");
my $redint=($ipob->intip());
$redint = Math::BigInt->new("$redint");
my $redbroad_int=($ipob->last_int());
$first_ip_int = $redint + 1;
my $start_ip_int=$first_ip_int;
$last_ip_int = ($ipob->last_int());
$last_ip_int = Math::BigInt->new("$last_ip_int");
$last_ip_int = $last_ip_int - 1;



my @ch=$gip->get_host("$client_id","$ip_int","$ip_int");
$ch[0]->[1] = "---" if $ch[0]->[1] eq "NULL";
$ch[0]->[2] = "---" if $ch[0]->[2] eq "NULL";
$ch[0]->[3] = "---" if $ch[0]->[3] eq "NULL";
$ch[0]->[4] = "---" if $ch[0]->[4] eq "NULL";
$ch[0]->[6] = "---" if $ch[0]->[6] eq "NULL";
$ch[0]->[7] = "---" if ! $ch[0]->[7] || $ch[0]->[7] eq "NULL";

my $host_id = $ch[0]->[11];


my $range_comentario=$gip->get_rango_comentario_host("$client_id","$ip_int");
if ( $range_comentario ) {
	$gip->clear_ip("$client_id","$ip_int","$ip_int");
} else {
	$gip->delete_ip("$client_id","$ip_int","$ip_int");
}
$gip->delete_custom_host_column_entry("$client_id","$host_id");

my ($host_hash_ref,$host_sort_helper_array_ref)=$gip->get_host_hash("$client_id","$first_ip_int","$last_ip_int","$host_order_by","$knownhosts");

my @switches;
my @switches_new;
if ( $host_hash_ref->{$first_ip_int}[12] ) {
	my $switch_id_hash = $host_hash_ref->{$first_ip_int}[12];
	@switches = $gip->get_vlan_switches_match("$client_id","$switch_id_hash");
	my $i = 0;
	if (scalar(@switches) == 0) {
		foreach ( @switches ) {
			my $vlan_id = $_[0];
			my $switches = $_[1];
			$switches =~ s/,$switch_id_hash,/,/;
			$switches =~ s/^$switch_id_hash,//;
			$switches =~ s/,$switch_id_hash$//;
			$switches =~ s/^$switch_id_hash$//;
			$switches_new[$i]->[0]=$vlan_id;
			$switches_new[$i]->[1]=$switches;
			$i++;
		}

		foreach ( @switches_new ) {
			my $vlan_id_new = $_[0];
			my $switches_new = $_[1];
			$gip->update_vlan_switches("$client_id","$vlan_id_new","$switches_new");
		}
	}
}
		


my $audit_type="14";
my $audit_class="1";
my $update_type_audit="1";
my $event="$ip_ad,$ch[0]->[1],$ch[0]->[2],$ch[0]->[3],$ch[0]->[4],$ch[0]->[5],$ch[0]->[6],$ch[0]->[7] ";
$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");

my $red_loc = $gip->get_loc_from_redid("$client_id","$red_num");


my $anz_host_total=$gip->get_host_hash_count("$client_id","$first_ip_int","$last_ip_int","$host_order_by","$red_num","$knownhosts") || "0";


if ( $anz_host_total >= $entries_per_page_hosts ) {
        my $last_ip_int_new = $first_ip_int + $start_entry_hosts + $entries_per_page_hosts - 1;
        $last_ip_int = $last_ip_int_new if $last_ip_int_new < $last_ip_int;
} else {
        $last_ip_int = ($ipob->last_int());
        $last_ip_int = $last_ip_int - 1;
}

my %anz_hosts_bm = $gip->get_anz_hosts_bm_hash("$client_id","$ip_version");
my $anz_values_hosts_pages=$anz_hosts_bm{$BM};
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

my $pages_links=$gip->get_pages_links_host("$client_id","$start_entry_hosts","$anz_values_hosts_pages","$entries_per_page_hosts","$red_num","$knownhosts","$host_order_by","$start_ip_int",$host_hash_ref,"$redbroad_int","$ip_version");

$gip->PrintIpTabHead("$client_id","$knownhosts","res/ip_modip_form.cgi","$red_num","$vars_file","$start_entry_hosts","$anz_values_hosts","$entries_per_page_hosts","$pages_links","$host_order_by","$ip_version");

$gip->PrintIpTab("$client_id",$host_hash_ref,"$first_ip_int","$last_ip_int","res/ip_modip_form.cgi","$knownhosts","$$lang_vars{modificar_message}","$red_num","$red_loc","$vars_file","$anz_values_hosts_pages","$start_entry_hosts","$entries_per_page_hosts","$host_order_by",$host_sort_helper_array_ref,"","$ip_version");

$gip->print_end("$client_id","$vars_file");
