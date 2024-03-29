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
use Net::IP;
use Net::IP qw(:PROC);
use lib '../modules';
use GestioIP;

my $daten=<STDIN>;
my $gip = GestioIP -> new();
my %daten=$gip->preparer($daten);

my $lang = $daten{'lang'} || "";
my ($lang_vars,$vars_file,$entries_per_page);
if ( $daten{'entries_per_page'} ) {
        $daten{'entries_per_page'} = "500" if $daten{'entries_per_page'} !~ /^\d{1,3}$/;
        ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("$daten{'entries_per_page'}","$lang");
} else {
        ($lang_vars,$vars_file,$entries_per_page)=$gip->get_lang("","$lang");
}

my $client_id = $daten{'client_id'} || $gip->get_first_client_id();
my $ip_version = $daten{'ip_version'} || "v4";

my @global_config = $gip->get_global_config("$client_id");
my $global_ip_version=$global_config[0]->[5] || "v4";
my $ip_version_ele="";
if ( $global_ip_version ne "yes" ) {
##### TEST
	$ip_version_ele = $ip_version || "";
	if ( $daten{'ip_version_ele'} ) {
		$ip_version_ele = $daten{'ip_version_ele'} if ! $ip_version_ele;
	}
        if ( $ip_version_ele ) {
                $ip_version_ele = $gip->set_ip_version_ele("$ip_version_ele");
        } else {
                $ip_version_ele = $gip->get_ip_version_ele();
        }

} else {
	$ip_version_ele = "$ip_version";
}

my $rootnet = $daten{'rootnet'} || "n";
my $rootnet_val = "0";
$rootnet_val = "1" if $rootnet eq "y";

$gip->CheckInput("$client_id",\%daten,"$$lang_vars{mal_signo_error_message}","$$lang_vars{crear_red_message}","$vars_file");

$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (1)") if $ip_version !~ /(v4|v6)/; 

my $start_entry=$daten{'start_entry'} || '0';
$gip->print_error("$client_id","$$lang_vars{formato_malo_message} (3)") if $start_entry !~ /^\d{1,4}$/;
my $tipo_ele = $daten{'tipo_ele'} || "NULL";
my $loc_ele = $daten{'loc_ele'} || "NULL";
my $order_by = $daten{'order_by'} || "red_auf";

my ($new_redes, $new_redes_count);
my (@new_redes, @new_redes_detail);
if ( $daten{new_redes} ) {
## multiple redes
	if ( $ip_version eq "v4" ) {
		if ( $daten{new_redes} !~ /(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2}-?)+(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\/\d{1,2})*$/ ) { $gip->print_error("$client_id","$$lang_vars{formato_malo_message}") };
	} else {
#### TEST
#		$gip->check_valid_ipv6("$daten{new_redes}");
	}
	$new_redes = $daten{new_redes};
	@new_redes=split('-',$daten{new_redes});
	$new_redes_count = @new_redes;

	for (my $l=0; $l <= $new_redes_count; $l++) {
		$new_redes_detail[$l]->[0] = $daten{"red_$l"};
		$new_redes_detail[$l]->[1] = $daten{"BM_$l"};
		$new_redes_detail[$l]->[2] = $daten{"descr_$l"} || "NULL";
		$new_redes_detail[$l]->[3] = $daten{"loc_$l"} || "NULL";
		$new_redes_detail[$l]->[4] = $daten{"cat_net_$l"} || "NULL";
		$new_redes_detail[$l]->[5] = $daten{"comentario_$l"} || "NULL";
		$new_redes_detail[$l]->[6] = $daten{"vigilada_$l"} || "n";
	}
	my $m = "0";
	my $event;
	foreach my $ele (@new_redes_detail) {
	if ( ! $ele || ! $new_redes_detail[$m]->[0] ) { next; }

		my $red_nuevo=$new_redes_detail[$m]->[0];
		my $BM_nuevo=$new_redes_detail[$m]->[1];
		my $descr_nuevo = $new_redes_detail[$m]->[2] || "NULL";
		my $loc_nuevo = $new_redes_detail[$m]->[3] || "-1";
		my $loc_id_nuevo=$gip->get_loc_id("$client_id","$loc_nuevo") || "-1";
		my $cat_nuevo = $new_redes_detail[$m]->[4] || "-1";
		my $cat_id_nuevo=$gip->get_cat_net_id("$client_id","$cat_nuevo") || "-1";
		my $comentario_nuevo = $new_redes_detail[$m]->[5] || "NULL";
		my $vigilada_nuevo = $new_redes_detail[$m]->[6] || "n";

		my $redob = $red_nuevo . "/" . $BM_nuevo;
		my $ipob = new Net::IP ($redob) or $gip->print_error("$client_id","$$lang_vars{formato_malo_message}<b>$redob</b>");
		my $red_exists = $gip->check_red_exists("$client_id",$red_nuevo,$BM_nuevo);
		if ( $red_exists ) {
			$gip->print_error("$client_id","$$lang_vars{red_exists_message} $redob");
		}
		my $red_id_nuevo=$gip->get_last_red_num("$client_id");
		$red_id_nuevo++;
		$gip->insert_net("$client_id","$red_id_nuevo","$red_nuevo","$BM_nuevo","$descr_nuevo","$loc_id_nuevo","$vigilada_nuevo","$comentario_nuevo","$cat_id_nuevo","$ip_version","$rootnet_val") or die $gip->print_error("$client_id");
		print "<p><b>$$lang_vars{redes_nuevos_done_message}</b><p>\n" if $m == "0";
		print "$red_nuevo/$BM_nuevo</b><br>\n";

		#audit
		my $audit_type="17";
		my $audit_class="2";
		my $update_type_audit="1";
		$descr_nuevo = "---" if $descr_nuevo eq "NULL";
		$loc_nuevo = "---" if $loc_nuevo eq "NULL";
		$cat_nuevo = "---" if $cat_nuevo eq "NULL";
		$comentario_nuevo = "---" if $comentario_nuevo eq "NULL";
		$event = "$red_nuevo/$BM_nuevo,$descr_nuevo,$loc_nuevo,$cat_nuevo,$comentario_nuevo,$vigilada_nuevo" if $new_redes_detail[$m]->[0];
		$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
		$m++;
	}

} else {
## one red

	if ( $daten{'BM'} =~ /^(\d\d\d).*/ ) {
		$daten{'BM'} =~ /^(\d\d\d).*/;
		$daten{'BM'} = $1;
	} elsif ( $daten{'BM'} =~ /^(\d\d).*/ ) {
		$daten{'BM'} =~ /^(\d\d).*/;
		$daten{'BM'} = $1;
	} elsif ( $daten{'BM'} =~ /^(\d).*/ ) {
		$daten{'BM'} =~ /^(\d).*/;
		$daten{'BM'} = $1;
	}


	my $red = $daten{'red'}  || $gip->print_error("$client_id","$$lang_vars{introduce_red_id_message}");

	$red =~ s/^\+*//;
	$red =~ s/\s*$//;
	my $BM = $daten{'BM'} || $gip->print_error("$client_id","$$lang_vars{introduce_BM_message}");
	my $descr = $daten{'descr'} || $gip->print_error("$client_id","$$lang_vars{introduce_description_message}");
	my $loc = $daten{'loc'} || $gip->print_error("$client_id","$$lang_vars{introduce_loc_message}");
	my $cat_net = $daten{'cat_red'} || $gip->print_error("$client_id","$$lang_vars{cat_red_message}");
	my $comentario = $daten{'comentario'} || "NULL";
	my $vigilada = $daten{'vigilada'} || "n";

	if ( $ip_version eq "v4" ) {
		$gip->CheckInIP("$client_id","$red","$$lang_vars{formato_red_malo_message} - $$lang_vars{comprueba_red_id_message}<br>");
	} else {
		my $valid_v6 = $gip->check_valid_ipv6("$red") || "0";
		$gip->print_error("$client_id","$$lang_vars{'no_valid_ipv6_address_message'}: <b>$red</b>") if $valid_v6 != "1";
	}

	my $loc_id=$gip->get_loc_id("$client_id","$loc");
	my $cat_net_id=$gip->get_cat_net_id("$client_id","$cat_net");

	my ( $broad,$mask,$hosts) = $gip->get_red_nuevo("$client_id","$red","$BM","$vars_file");

	my $check_exist_red = $red;
	$check_exist_red= ip_expand_address ($red,6) if $ip_version eq "v6";
	my $red_check=$gip->check_red_exists("$client_id","$check_exist_red","$BM");
	if ( $red_check ) {
		$gip->print_error("$client_id","$$lang_vars{red_exists_message}: <b>$red</b>");
	}
print "TEST3: $red<br>\n";

	my $ip = new Net::IP ("$red/$BM") or $gip->print_error("$client_id","$$lang_vars{comprueba_red_BM_message}: <b>$red/$BM</b> (1)");


	if ( $rootnet eq "n" ) {
		my @overlap_redes=$gip->get_overlap_red("$ip_version","$client_id");

		# Check for overlapping networks
		if ( $overlap_redes[0]->[0] ) {
			my @overlap_found = $gip->find_overlap_redes("$client_id","$red","$BM",\@overlap_redes,"$ip_version",$vars_file);
			if ( $overlap_found[0] ) {
				$gip->print_error("$client_id","$red/$BM $$lang_vars{overlaps_con_message} $overlap_found[0]");
				next;
			}
		}
	}

	my $red_num=$gip->get_last_red_num("$client_id");
	$red_num = "0" if ( ! $red_num );
	my $new_red_num=$red_num + 1;
	$red = ip_expand_address ($red,6) if $ip_version eq "v6";
#	$gip->insert_net("$client_id","$new_red_num","$red","$BM","$descr","$loc_id","$vigilada","$comentario","$cat_net_id","$ip_version");
	$gip->insert_net("$client_id","$new_red_num","$red","$BM","$descr","$loc_id","$vigilada","$comentario","$cat_net_id","$ip_version","$rootnet_val");
	my $audit_type="17";
	my $audit_class="2";
	my $update_type_audit="1";
	$descr="---" if $descr eq "NULL";
	$comentario="---" if $comentario eq "NULL";

	my $event="$red/$BM,$descr,$loc,$cat_net,$comentario,$vigilada";
	$gip->insert_audit("$client_id","$audit_class","$audit_type","$event","$update_type_audit","$vars_file");
	print "<p><b>$$lang_vars{redes_nuevo_done_message}: $red/$BM</b><p>\n";
}


my $tipo_ele_id= "-1";
my $loc_ele_id= "-1";
my $anz_values_redes = $gip->count_red_entries_all("$client_id","$tipo_ele","$loc_ele");
my $pages_links=$gip->get_pages_links_red("$client_id","$start_entry","$anz_values_redes","$entries_per_page","$tipo_ele","$loc_ele");
my @ip=$gip->get_redes("$client_id","$tipo_ele_id","$loc_ele_id","$start_entry","$entries_per_page","$order_by","$ip_version");
my $ip=$gip->prepare_redes_array("$client_id",\@ip,"$order_by","$start_entry","$entries_per_page","$ip_version");

$gip->PrintRedTabHead("$client_id","$vars_file","$start_entry","$entries_per_page","$pages_links","$tipo_ele","$loc_ele","$ip_version");

if ( @ip ) {
        $gip->PrintRedTab("$client_id",\@ip,"$vars_file","simple","","","","","","","","$ip_version");
} else {
        print "<p class=\"NotifyText\">$$lang_vars{no_resultado_message}</p><br>\n";
}


$gip->print_end("$client_id","$vars_file","go_to_top");
