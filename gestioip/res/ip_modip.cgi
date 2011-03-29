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

my %daten=$gip->preparer($daten);

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page_hosts);
($lang_vars,$vars_file)=$gip->get_lang("","$lang");
if ( $daten{'entries_per_page_hosts'} && $daten{'entries_per_page_hosts'} =~ /^\d{1,4}$/ ) {
        $entries_per_page_hosts=$daten{'entries_per_page_hosts'};
} else {
        $entries_per_page_hosts = "254";
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $ip_version = $daten{'ip_version'};

my ($hostname, $ip);
if ( $ip_version eq "v4" ) {
	$ip=$daten{'ip'} if ( $daten{'ip'} =~ /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/ );
} else {
	$ip=$daten{'ip'};
}
my $host_order_by = $daten{'host_order_by'} || "IP_auf";


my $length_hostname = length($daten{'hostname'});
my $length_descr = length($daten{'host_descr'});
my $length_comentario = length($daten{'comentario'});
my ($ipob, $ip_int, $range_comentario);


if ( ! $daten{'hostname'} || ! $daten{'loc'} || ! $ip || $daten{'hostname'} =~ /\s+/ || $length_hostname > 45 || $length_hostname < 2 || $length_descr > 100 || $length_comentario > 500) {
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{cambiar_host_message} $daten{'ip'}","$vars_file");
	$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if ! $ip;
	$ipob = new Net::IP ($ip) or $gip->print_error("$client_id","$$lang_vars{formato_ip_malo_message}: <b>+$ip+</b>");
	$ip_int = ($ipob->intip());
	$range_comentario=$gip->get_rango_comentario_host("$client_id","$ip_int");
	$gip->print_error("$client_id","$$lang_vars{introduce_hostname_message}") if ! $daten{'hostname'};
	$gip->print_error("$client_id","$$lang_vars{min_signos_hostname_message}") if $length_hostname < 2;
	$gip->print_error("$client_id","$$lang_vars{introduce_loc_message}") if ! $daten{'loc'};
	$gip->print_error("$client_id","$$lang_vars{whitespace_message}") if $daten{'hostname'} =~ /\s+/;
	$gip->print_error("$client_id","$$lang_vars{max_signos_hostname_message}") if $length_hostname > 45;
	$gip->print_error("$client_id","$$lang_vars{max_signos_descr_message}") if $length_hostname > 100;
	$gip->print_error("$client_id","$$lang_vars{max_signos_comentario_message}") if $length_hostname > 500;
} else { 
	$hostname=$daten{'hostname'} || "$ip";
	$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$hostname: $$lang_vars{cambiar_host_done_message}","$vars_file");
	$ipob = new Net::IP ($ip) or $gip->print_error("$client_id","$$lang_vars{formato_ip_malo_message}: <b>+$ip+</b>");
	$ip_int = ($ipob->intip());
	$range_comentario=$gip->get_rango_comentario_host("$client_id","$ip_int");
}


my $loc=$daten{'loc'} || "NULL";
my $red=$daten{'red'};
my $BM=$daten{'BM'};
my $red_num=$daten{'red_num'};
my $host_descr=$daten{'host_descr'} || "NULL";
my $cat=$daten{'cat'} || "NULL";
my $host_exist=$daten{'host_exist'};
my $comentario=$daten{'comentario'} || "NULL";
my $knownhosts = $daten{'knownhosts'} || "all";
my $int_admin = $daten{'int_admin'} || "n";
my $utype = $daten{'update_type'};
my $host_id = $daten{'host_id'} || "";

$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'anz_values_hosts'} && $daten{'anz_values_hosts'} !~ /^\d{2,4}||no_value$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'knownhosts'} && $daten{'knownhosts'} !~ /^all|hosts|libre$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message}") if $daten{'start_entry_hosts'} && $daten{'start_entry_hosts'} !~ /^\d{1,20}$/;
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (2)") if $ip_version !~ /^(v4|v6)$/;


my $redob = "$red/$BM";
my $loc_id=$gip->get_loc_id("$client_id","$loc") || "-1";
my $cat_id=$gip->get_cat_id("$client_id","$cat") || "-1";
my $utype_id=$gip->get_utype_id("$client_id","$utype") || "-1";
my $start_entry_hosts=$daten{'start_entry_hosts'} || '0';


my ( $first_ip_int, $last_ip_int, $start_entry);

$ipob = new Net::IP ($redob) || $gip->print_error("$client_id","Can't create ip object: $!\n");
my $redint=($ipob->intip());
my $redbroad_int=($ipob->last_int());
$redint = Math::BigInt->new("$redint");
$first_ip_int = $redint + 1;
my $start_ip_int=$first_ip_int;
$last_ip_int = ($ipob->last_int());
$last_ip_int = Math::BigInt->new("$last_ip_int");
$last_ip_int = $last_ip_int - 1;


my $mydatetime = time();

my $red_loc = $gip->get_loc_from_redid("$client_id","$red_num");
my @ch=$gip->get_host("$client_id","$ip_int","$ip_int");

if ( @ch ) {
	my $alive = $ch[0]->[8] || "-1";
	$gip->update_ip_mod("$client_id","$ip_int","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","$alive");
} else {
	$gip->insert_ip_mod("$client_id","$ip_int","$hostname","$host_descr","$loc_id","$int_admin","$cat_id","$comentario","$utype_id","$mydatetime","$red_num","-1","$ip_version");
}


$host_id = $gip->get_last_host_id("$client_id") if ! $host_id;

my %cc_value=$gip->get_custom_host_columns_id_from_net_id_hash("$client_id","$red_num");
my @custom_columns = $gip->get_custom_host_columns("$client_id");
my $cc_anz=@custom_columns;

my $audit_entry_cc;
my $audit_entry_cc_new;

for (my $o=0; $o<$cc_anz; $o++) {
        my $cc_name=$daten{"custom_${o}_name"};
        my $cc_value=$daten{"custom_${o}_value"};
        my $cc_id=$daten{"custom_${o}_id"};
        my $pc_id=$daten{"custom_${o}_pcid"};

        if ( $daten{"custom_${o}_value"} ) {
                my $cc_entry_host=$gip->get_custom_host_column_entry("$client_id","$host_id","$cc_name","$pc_id") || "";
                if ( $cc_entry_host ) {
                        $gip->update_custom_host_column_value_host_modip("$client_id","$cc_id","$pc_id","$host_id","$cc_value");
			if ( $audit_entry_cc ) {
				$audit_entry_cc = $audit_entry_cc . "," . $cc_entry_host;
			} else {
				$audit_entry_cc = $cc_entry_host;
			}
			if ( $audit_entry_cc_new ) {
				$audit_entry_cc_new = $audit_entry_cc_new . "," .$cc_value;
			} else {
				$audit_entry_cc_new = $cc_value;
			}
                } else {
                        $gip->insert_custom_host_column_value_host("$client_id","$cc_id","$pc_id","$host_id","$cc_value");
			if ( $audit_entry_cc ) {
				$audit_entry_cc = $audit_entry_cc . ",---";
			} else {
				$audit_entry_cc = ",---";
			}
			if ( $audit_entry_cc_new ) {
				$audit_entry_cc_new = $audit_entry_cc_new . "," . $cc_value ;
			} else {
				$audit_entry_cc_new = $cc_value;
			}
                }
        } else {
                my $cc_entry_host=$gip->get_custom_host_column_entry("$client_id","$host_id","$cc_name","$pc_id") || "";
                if ( $cc_entry_host ) {
			$gip->delete_single_custom_host_column_entry("$client_id","$host_id","$cc_entry_host","$pc_id");
			if ( $audit_entry_cc ) {
				$audit_entry_cc = $audit_entry_cc . "," . $cc_entry_host;
			} else {
				$audit_entry_cc = $cc_entry_host;
			}
			if ( $audit_entry_cc_new ) {
				$audit_entry_cc_new = $audit_entry_cc_new . ",---" ;
			} else {
				$audit_entry_cc_new = "---";
			}
		} else {
			if ( $audit_entry_cc ) {
				$audit_entry_cc = $audit_entry_cc . ",---";
			} else {
				$audit_entry_cc = "---";
			}
			if ( $audit_entry_cc_new ) {
				$audit_entry_cc_new = $audit_entry_cc_new . ",---" ;
			} else {
				$audit_entry_cc_new = "---";
			}
		}
	}
}

$audit_entry_cc = "---" if ! $audit_entry_cc;
$audit_entry_cc_new = "---" if ! $audit_entry_cc_new;


if ( @ch ) {
	my $audit_class="1";
	my $audit_type="1";
	my $update_type_audit="1";
	$utype = "---" if ! $utype;
	$ch[0]->[1] = "---" if ! $ch[0]->[1];
	$ch[0]->[1] = "---" if $ch[0]->[1] eq "NULL";
	$ch[0]->[2] = "---" if ! $ch[0]->[2];
	$ch[0]->[2] = "---" if $ch[0]->[2] eq "NULL";
	$ch[0]->[3] = "---" if $ch[0]->[3] eq "NULL";
	$ch[0]->[4] = "---" if $ch[0]->[4] eq "NULL";
	$ch[0]->[6] = "---" if ! $ch[0]->[6];
	$ch[0]->[6] = "---" if $ch[0]->[6] eq "NULL";
	$ch[0]->[7] = "---" if ! $ch[0]->[7];
	$ch[0]->[7] = "---" if $ch[0]->[7] eq "-1" || $ch[0]->[7] eq "NULL";
	my $ip=$gip->int_to_ip("$client_id","$ip_int");
	$host_descr = "---" if $host_descr eq "NULL";
	$cat = "---" if $cat eq "NULL";
	$loc = "---" if $loc eq "NULL";
	$comentario = "---" if $comentario eq "NULL";
	$utype = "---" if ! $utype;
	my $hostname_audit = $hostname;
	$hostname_audit = "---" if $hostname_audit eq "NULL";
	if ( $range_comentario ) {
		if ( $comentario ne "---" ) {
			$comentario = "[" . $range_comentario . "] " . $comentario;
		} else {
			$comentario = "[" . $range_comentario . "] ";
		}
		if ( $ch[0]->[6] ne "---" ) {
			$ch[0]->[6] = "[" . $range_comentario . "] " . $ch[0]->[6];
		} else {
			$ch[0]->[6] = "[" . $range_comentario . "] ";
		}
	}
	my $event="$ip: $ch[0]->[1],$ch[0]->[2],$ch[0]->[3],$ch[0]->[4],$ch[0]->[5],$ch[0]->[6],$ch[0]->[7],$audit_entry_cc" . " -> " . "$hostname_audit,$host_descr,$loc,$int_admin,$cat,$comentario,$utype,$audit_entry_cc_new";
	$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
} else {
	my $audit_type="15";
	my $audit_class="1";
	my $update_type_audit="1";
	$host_descr = "---" if $host_descr eq "NULL";
	$cat = "---" if $cat eq "NULL";
	$loc = "---" if $loc eq "NULL";
	$comentario = "---" if $comentario eq "NULL";
	$utype = "---" if ! $utype;
	my $hostname_audit = $hostname;
	$hostname_audit = "---" if $hostname_audit eq "NULL";
	my $event="$ip: $hostname_audit,$host_descr,$loc,$int_admin,$cat,$comentario,$utype";
	$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
}


my ($host_hash_ref,$host_sort_helper_array_ref)=$gip->get_host_hash("$client_id","$first_ip_int","$last_ip_int","$host_order_by","$knownhosts");

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

$gip->PrintIpTabHead("$client_id","$knownhosts","res/ip_modip_form.cgi","$red_num","$vars_file","$start_entry_hosts","$anz_values_hosts","$entries_per_page_hosts","$pages_links","","$ip_version");

$gip->PrintIpTab("$client_id",$host_hash_ref,"$first_ip_int","$last_ip_int","res/ip_modip_form.cgi","$knownhosts","$$lang_vars{modificar_message}","$red_num","$red_loc","$vars_file","$anz_values_hosts_pages","$start_entry_hosts","$entries_per_page_hosts","$host_order_by","$host_sort_helper_array_ref","","$ip_version");



$gip->print_end("$client_id","$vars_file","go_to_top");
